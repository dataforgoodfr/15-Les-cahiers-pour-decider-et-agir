"""OCR modernes contre ABBYY, sur l'édition Chabin (issue #12).

    uv run python -m ocr.modernes transcrire --modele lightonocr-2 [--url …]
    uv run python -m ocr.modernes transcrire --modele tesseract
    uv run python -m ocr.modernes mesurer

La couche texte du versement (ABBYY FineReader Engine 11) lit bien la
contribution typique, mal une queue de pages (`docs/ocr.md`). On essaie des
OCR récents à poids ouverts sur les mêmes contributions de l'édition Chabin :

- `ovisocr3` (ATH-MaaS, 0,8 Md, Apache 2.0), en texte, et `ovisocr3-mots`,
  son mode qui rend chaque mot avec son cadre, comme la couche ABBYY ;
- `lightonocr-2` (LightOn, 1 Md, Apache 2.0) ;
- `chandra-2` (Datalab, 5 Md, OpenRAIL-M modifiée : gratuite sous 2 M$ de
  revenus), en HTML, dont on ne garde que le texte ;
- `tesseract`, sur cette machine, sans carte : le point de comparaison sobre.

Les modèles sont servis par vLLM sur une carte louée en Europe, jointe par
un tunnel (`--url`), comme pour `anonymisation.vision`. Chaque page est
envoyée en image ; sa transcription est gardée dans `data/` (jamais dans
git, jamais affichée). Les pages lues sont, pour chaque contribution
dactylographiée ou imprimée d'une messagerie retrouvée par `decoupage.chabin`, sa
première page et les pages dactylographiées jusqu'à la contribution
suivante.

`mesurer` compare chaque source à la transcription de Marie-Anne Chabin,
ABBYY compris, sur les mêmes pages : la contribution est cherchée dans le
texte des pages (alignement local : début et fin libres), puis on compte le
CER, le WER, et la nature des écarts mot à mot, comme au banc HTR
(`invention.py`) : mal lu, inventé (un autre mot français, invisible sans
l'image), charabia, omis. Écrit `modernes.md` dans la sortie. Des taux,
jamais de texte.
"""

import argparse
import csv
import html
import json
import random
import re
import subprocess
import time
import urllib.error
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pymupdf
from wordfreq import zipf_frequency

from anonymisation.vision import URL, interroger_modele
from corpus.communes import sources
from decoupage.contributions.__main__ import lignes
from ocr.anomalies import ALPHA, LEXIQUE, _simple
from ocr.chabin import CROCHETS, flux, lire_alignement, normalisee, sans_accents
from panels.panel.panel import lire_typage

DACTYLOGRAPHIEE = "dactylographiée"
CONSIGNE_OVIS = (
    "Read all the text in the image. Directly output the content.\n\n"
    "Rules:\n"
    "1. Preserve the original text exactly without translation, paraphrasing, "
    "correction, or completion.\n"
    "2. Follow the natural human reading order.\n"
    "3. Output plain text only. Use spaces and line breaks only to preserve text "
    "separation and reading order.\n"
    "4. Do not output Markdown, HTML, JSON, bounding boxes, category labels, "
    "explanations, or code fences."
)
CONSIGNE_OVIS_MOTS = (
    "Locate and transcribe every readable word or text token in the image. "
    "Return a single JSON array in natural reading order.\n\n"
    "Each element follows this schema:\n"
    '`{"bbox": [x_min, y_min, x_max, y_max], "text": "string"}`\n\n'
    "Rules:\n"
    "1. Use word-level annotations. Each element must represent exactly one "
    "visible word or text token. Do not merge multiple words into a text line, "
    "paragraph, label, or table cell.\n"
    "2. The bbox coordinates are integers scaled to [0, 1000).\n"
    "3. Each bbox must tightly enclose its corresponding visible word or text "
    "token and must not include adjacent words or unrelated text regions.\n"
    "4. Preserve the original text exactly without translation, paraphrasing, "
    "correction, or completion.\n"
    "5. Do not add leading or trailing whitespace to text.\n"
    "6. Include every readable word or text token and exclude non-text visual "
    "content.\n"
    "7. Output strictly valid JSON only. Do not output Markdown, explanations, or "
    "code fences. Properly escape quotes, backslashes, and other special "
    "characters inside text."
)
# la consigne « ocr » de Chandra (chandra/prompts.py), sans ses consignes de
# mise en forme des formules, schémas et images, inutiles ici
CONSIGNE_CHANDRA = (
    "OCR this image to HTML.\n\n"
    "Guidelines:\n"
    "* Tables: Use colspan and rowspan attributes to match table structure.\n"
    "* Forms: Mark checkboxes and radio buttons properly.\n"
    "* Text: join lines together properly into paragraphs using <p>...</p> tags.\n"
    "* Make sure the text is accurate and easy for a human to read and interpret. "
    "Reading order should be correct and natural."
)
# dépôt, consigne, options de vLLM, plafond de jetons, résolution (points par
# pouce) et plus long côté de l'image en pixels
MODELES = {
    "ovisocr3": {
        "depot": "ATH-MaaS/OvisOCR3",
        "consigne": CONSIGNE_OVIS,
        "options": {"chat_template_kwargs": {"enable_thinking": False}},
        "max_tokens": 8192,
        "dpi": 200,
        "cote": 2880,
    },
    "ovisocr3-mots": {
        "depot": "ATH-MaaS/OvisOCR3",
        "servi": "ovisocr3",
        "consigne": CONSIGNE_OVIS_MOTS,
        "options": {"chat_template_kwargs": {"enable_thinking": False}},
        "max_tokens": 16384,
        "dpi": 200,
        "cote": 2880,
    },
    "lightonocr-2": {
        "depot": "lightonai/LightOnOCR-2-1B",
        "consigne": None,
        "options": {"temperature": 0.2, "top_p": 0.9},
        "max_tokens": 4096,
        "dpi": 200,
        "cote": 1540,
    },
    "chandra-2": {
        "depot": "datalab-to/chandra-ocr-2",
        "consigne": CONSIGNE_CHANDRA,
        "options": {},
        "max_tokens": 8192,
        "dpi": 200,
        "cote": 2048,
    },
    "tesseract": {"dpi": 300, "cote": 4000},
}
CATEGORIES = ("mal_lu", "invente", "charabia", "omis")
QUEUE = 0.10  # CER d'ABBYY au-delà duquel une contribution est dans la queue
HORS_LEXIQUE = 0.5  # part des mots hors lexique d'une page presque illisible
MOTS_MIN = 20  # mots lus au moins par ABBYY pour juger une page


def texte_brut(reponse: str, modele: str) -> str:
    """Le texte d'une réponse, sans balises HTML ni marques de Markdown, ou
    les mots d'une réponse en JSON (`ovisocr3-mots`) dans leur ordre."""
    if modele == "ovisocr3-mots":
        debut, fin = reponse.find("["), reponse.rfind("]")
        mots = json.loads(reponse[debut : fin + 1]) if debut >= 0 < fin else []
        return " ".join(str(m.get("text", "")) for m in mots if isinstance(m, dict))
    texte = re.sub(r"<[^>]+>", " ", reponse)
    texte = re.sub(r"(\*\*|__|^#+\s|^\s*[-*]\s|\|)", " ", texte, flags=re.MULTILINE)
    return html.unescape(texte)


def image(page: pymupdf.Page, dpi: int, cote: int, format_: str = "jpeg") -> bytes:
    """La page en image : en JPEG pour les modèles servis (sept fois moins
    lourd qu'en PNG à envoyer par le tunnel), en PNG pour Tesseract."""
    plus_long = max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(dpi=min(dpi, int(cote * 72 / plus_long)))
    if format_ == "jpeg":
        return pix.tobytes("jpg", jpg_quality=90)
    return pix.tobytes("png")


def tesseract(png: bytes) -> str:
    return subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "fra"],
        input=png,
        capture_output=True,
        check=True,
    ).stdout.decode()


def contributions_de_chabin(args) -> list[dict]:
    """Les contributions imprimées retrouvées par `decoupage.chabin`, avec leur
    transcription et les pages à lire : (fichier, numéro)."""
    extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
    alignement = lire_alignement(args.alignement)
    types = {
        (t["fichier"], int(t["page"])): t["type_page"]
        for t in lire_typage([args.typage])
    }
    chemins = {p.name: p for p in args.versement.rglob("*.pdf")}
    sortie = []
    for e in extraction:
        if not e or e["city"]["insee"] not in alignement:
            continue
        trouvees = alignement[e["city"]["insee"]]
        lignes_ocr = flux([chemins[Path(f).name] for f in e["pdf_files"]])
        position = {(f, n, i): k for k, (f, n, i, _) in enumerate(lignes_ocr)}
        debuts = sorted(position[a["fichier"], a["page"], a["ligne"]] for a in trouvees)
        for a in trouvees:
            debut = position[a["fichier"], a["page"], a["ligne"]]
            suivant = next((d for d in debuts if d > debut), len(lignes_ocr))
            pages = [(a["fichier"], a["page"])]
            for f, n, _, _ in lignes_ocr[debut:suivant]:
                if (f, n) not in pages and types.get((f, n)) == DACTYLOGRAPHIEE:
                    pages.append((f, n))
            sortie.append(
                {
                    "insee": a["insee"],
                    "rang": a["rang"],
                    "genre": a["genre"],
                    "reference": CROCHETS.sub(
                        " ", e["contributions"][a["rang"] - 1]["text"]
                    ),
                    "pages": pages,
                }
            )
    return sortie


def chemin_texte(sortie: Path, modele: str, fichier: str, n: int) -> Path:
    return sortie / "modernes" / modele / f"{Path(fichier).stem}.{n}.txt"


def transcrire(args) -> None:
    m = MODELES[args.modele]
    cle = (
        args.cle.read_text(encoding="utf-8").strip()
        if args.modele != "tesseract"
        else ""
    )
    if args.pages:
        pages = lire_pages(args.pages)
    else:
        pages = sorted({p for c in contributions_de_chabin(args) for p in c["pages"]})
    chemins = {p.name: p for p in args.versement.rglob("*.pdf")}
    restantes = [
        (f, n)
        for f, n in pages
        if not chemin_texte(args.sortie, args.modele, f, n).exists()
    ]
    (args.sortie / "modernes" / args.modele).mkdir(parents=True, exist_ok=True)
    journal = args.sortie / "modernes" / f"{args.modele}.pages.csv"
    nouveau = not journal.exists()

    def une_page(png):
        debut, erreur, texte = time.monotonic(), "", ""
        try:
            if args.modele == "tesseract":
                texte = tesseract(png)
            else:
                reponse = interroger_modele(
                    args.url,
                    cle,
                    m.get("servi", args.modele),
                    png,
                    m["consigne"],
                    m["options"],
                    m["max_tokens"],
                    "jpeg",
                )
                texte = texte_brut(reponse, args.modele)
        except (
            ValueError,
            urllib.error.URLError,
            TimeoutError,
            subprocess.CalledProcessError,
        ) as e:
            # le type de l'erreur seulement : son message peut citer la page
            erreur = type(e).__name__
        return texte, round(time.monotonic() - debut, 1), erreur

    with journal.open("a", encoding="utf-8", newline="") as fj:
        ecrit = csv.DictWriter(fj, ["fichier", "page", "secondes", "erreur"])
        if nouveau:
            ecrit.writeheader()
        en_cours, k = {}, 0
        with ThreadPoolExecutor(args.paralleles) as pool:
            for cle_page in [*restantes, None]:
                if cle_page is not None:
                    fichier, n = cle_page
                    with pymupdf.open(chemins[fichier]) as doc:
                        png = image(
                            doc[n - 1],
                            m["dpi"],
                            m["cote"],
                            "png" if args.modele == "tesseract" else "jpeg",
                        )
                    en_cours[pool.submit(une_page, png)] = cle_page
                    if len(en_cours) < args.paralleles:
                        continue
                    finis = wait(en_cours, return_when=FIRST_COMPLETED)[0]
                else:
                    finis = list(en_cours)
                for futur in finis:
                    fichier, n = en_cours.pop(futur)
                    texte, secondes, erreur = futur.result()
                    if not erreur:
                        chemin_texte(args.sortie, args.modele, fichier, n).write_text(
                            texte, encoding="utf-8"
                        )
                    ecrit.writerow(
                        {
                            "fichier": fichier,
                            "page": n,
                            "secondes": secondes,
                            "erreur": erreur,
                        }
                    )
                    fj.flush()
                    k += 1
                    print(
                        f"{k}/{len(restantes)}" + (f", {erreur}" if erreur else ""),
                        flush=True,
                    )


def _ligne_dp(ref: np.ndarray, hyp: np.ndarray, debut_libre: bool) -> np.ndarray:
    """La dernière ligne de la distance d'édition de `ref` aux débuts de
    `hyp` (début de `hyp` libre ou non)."""
    colonnes = np.arange(len(hyp) + 1)
    ligne = np.zeros(len(hyp) + 1, dtype=np.int64) if debut_libre else colonnes.copy()
    for i, r in enumerate(ref, start=1):
        precedente = ligne
        ligne = np.empty_like(precedente)
        ligne[0] = i
        ligne[1:] = np.minimum(precedente[:-1] + (hyp != r), precedente[1:] + 1)
        ligne = np.minimum.accumulate(ligne - colonnes) + colonnes
    return ligne


def alignement_local(reference: str, texte: str) -> tuple[int, int, int]:
    """La distance d'édition de `reference` au passage de `texte` qui lui
    ressemble le plus, et ce passage (début, fin), par caractères."""
    if not reference or not texte:
        return len(reference), 0, 0
    codes = {c: k for k, c in enumerate(dict.fromkeys(reference + texte))}
    ref = np.array([codes[c] for c in reference])
    hyp = np.array([codes[c] for c in texte])
    avant = _ligne_dp(ref, hyp, debut_libre=True)
    fin = int(np.argmin(avant))
    # le début : le même calcul à rebours, depuis la fin trouvée
    arriere = _ligne_dp(ref[::-1], hyp[:fin][::-1], debut_libre=False)
    longueur = int(np.argmin(arriere))
    return int(avant[fin]), fin - longueur, fin


def nature_des_ecarts(reference: list[str], texte: list[str]) -> dict[str, int]:
    """Les écarts mot à mot, classés comme au banc HTR (`invention.py`)."""
    n = dict.fromkeys(CATEGORIES, 0)

    def ajoute(mot):
        n["invente" if zipf_frequency(mot, "fr") >= 2 else "charabia"] += 1

    appariement = SequenceMatcher(None, reference, texte, autojunk=False)
    for op, i1, i2, j1, j2 in appariement.get_opcodes():
        if op == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                a = reference[i1 + k] if i1 + k < i2 else None
                b = texte[j1 + k] if j1 + k < j2 else None
                if a is None:
                    ajoute(b)
                elif b is None:
                    n["omis"] += 1
                elif SequenceMatcher(None, a, b).ratio() > 0.5:
                    n["mal_lu"] += 1
                else:
                    ajoute(b)
        elif op == "delete":
            n["omis"] += i2 - i1
        elif op == "insert":
            for b in texte[j1:j2]:
                ajoute(b)
    return n


def comparer(reference: str, texte: str) -> dict[str, float]:
    ref, hyp = sans_accents(reference), sans_accents(texte)
    distance, debut, fin = alignement_local(ref, hyp)
    passage = hyp[debut:fin]
    mots_ref, mots_hyp = ref.split(), passage.split()
    ecarts = nature_des_ecarts(mots_ref, mots_hyp)
    return {
        "caracteres": len(ref),
        "mots": len(mots_ref),
        "cer": distance / max(len(ref), 1),
        # le CER normalisé (accents compris), sur le même passage
        "cer accents": alignement_local(normalisee(reference), normalisee(texte))[0]
        / max(len(normalisee(reference)), 1),
        **ecarts,
    }


def mesurer(args) -> None:
    contributions = contributions_de_chabin(args)
    chemins = {p.name: p for p in args.versement.rglob("*.pdf")}
    modeles = [m for m in MODELES if (args.sortie / "modernes" / m).is_dir()]
    abbyy = {}
    for f, n in sorted({p for c in contributions for p in c["pages"]}):
        with pymupdf.open(chemins[f]) as doc:
            abbyy[f, n] = " ".join(t for t, _ in lignes(doc[n - 1]))
    resultats = defaultdict(list)
    for c in contributions:
        textes = {"abbyy": [abbyy[p] for p in c["pages"]]}
        for m in modeles:
            chemins_m = [chemin_texte(args.sortie, m, f, n) for f, n in c["pages"]]
            if all(p.exists() for p in chemins_m):
                textes[m] = [p.read_text(encoding="utf-8") for p in chemins_m]
        for source, pages in textes.items():
            resultats[source].append(
                {"insee": c["insee"], "rang": c["rang"]}
                | comparer(c["reference"], " ".join(pages))
            )
        print(f"{c['insee']} {c['rang']} : {len(textes)} sources", flush=True)
    queue = {(r["insee"], r["rang"]) for r in resultats["abbyy"] if r["cer"] > QUEUE}
    texte = rapport(resultats, queue, len(contributions))
    (args.sortie / "modernes.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


def rapport(resultats: dict, queue: set, total: int) -> str:
    lignes_ = [
        "# OCR modernes contre ABBYY, sur l'édition Chabin",
        "",
        (
            f"{total} contributions imprimées de Charente-Maritime. CER sans "
            "accents (et avec, normalisé) pondéré par la longueur, médiane entre "
            "parenthèses ; écarts mot à mot pour 100 mots de la référence. Une "
            "source n'est mesurée que sur les contributions dont elle a lu toutes "
            f"les pages. La queue : les {len(queue)} contributions où ABBYY "
            f"dépasse {QUEUE:.0%} de CER."
        ),
    ]
    for titre, garder in (
        ("Toutes", lambda r: True),
        ("La queue", lambda r: (r["insee"], r["rang"]) in queue),
    ):
        lignes_ += [
            "",
            f"## {titre}",
            "",
            (
                "| source | contributions | CER sans accents | CER normalisé "
                "| mal lus | inventés | charabia | omis |"
            ),
            "|---|---|---|---|---|---|---|---|",
        ]
        for source, liste in resultats.items():
            groupe = [r for r in liste if garder(r)]
            if not groupe:
                continue
            poids = np.array([r["caracteres"] for r in groupe], dtype=float)
            mots = sum(r["mots"] for r in groupe)

            def taux(cle, groupe=groupe, poids=poids):
                v = np.array([r[cle] for r in groupe])
                return f"{np.average(v, weights=poids):.1%} ({np.median(v):.1%})"

            lignes_.append(
                f"| {source} | {len(groupe)} | {taux('cer')} | {taux('cer accents')} | "
                + " | ".join(
                    f"{100 * sum(r[k] for r in groupe) / max(mots, 1):.1f}"
                    for k in CATEGORIES
                )
                + " |"
            )
    return "\n".join(lignes_)


def lire_pages(chemin: Path) -> list[tuple[str, int]]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return [(p["fichier"], int(p["page"])) for p in csv.DictReader(f)]


def illisibles(args) -> None:
    """Tire `--nombre` pages presque illisibles pour ABBYY (`ocr.anomalies` :
    plus de la moitié des mots hors lexique, au moins `MOTS_MIN` mots) et les
    écrit dans `illisibles.csv` de la sortie."""
    with (args.sortie / "anomalies.csv").open(encoding="utf-8", newline="") as f:
        candidates = [
            p
            for p in csv.DictReader(f)
            if float(p["hors_lexique"]) > HORS_LEXIQUE and float(p["mots"]) >= MOTS_MIN
        ]
    tirees = random.Random(args.graine).sample(candidates, args.nombre)
    with (args.sortie / "illisibles.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, ["fichier", "page", "departement"])
        ecrivain.writeheader()
        ecrivain.writerows({k: p[k] for k in ecrivain.fieldnames} for p in tirees)
    print(f"{len(tirees)} pages tirées sur {len(candidates)}")


def lexique(args) -> None:
    """Sur les pages de `--pages`, ABBYY contre chaque modèle qui les a lues :
    mots lus, et part des mots alphabétiques hors du lexique. Sans référence,
    c'est un indice de lisibilité, pas un taux d'erreur. Écrit
    `<pages>.md` à côté de la liste."""
    mots_du_lexique = {
        _simple(ligne.split("\t", 1)[0])
        for ligne in sources.telecharger(LEXIQUE, args.cache).decode().splitlines()[1:]
    }
    pages = lire_pages(args.pages)
    chemins = {p.name: p for p in args.versement.rglob("*.pdf")}
    textes = {"abbyy": {}}
    for f, n in pages:
        with pymupdf.open(chemins[f]) as doc:
            textes["abbyy"][f, n] = " ".join(t for t, _ in lignes(doc[n - 1]))
    for m in MODELES:
        lus = {
            (f, n): chemin_texte(args.sortie, m, f, n).read_text(encoding="utf-8")
            for f, n in pages
            if chemin_texte(args.sortie, m, f, n).exists()
        }
        if lus:
            textes[m] = lus

    def hors(texte):
        mots = [x for x in texte.split() if ALPHA.match(x.strip(".,;:!?()«»\"'"))]
        if not mots:
            return 1.0, 0
        dehors = sum(
            _simple(x.strip(".,;:!?()«»\"'")) not in mots_du_lexique for x in mots
        )
        return dehors / len(mots), len(texte.split())

    lignes_ = [
        f"# Pages de {args.pages.name} : ABBYY et les OCR modernes",
        "",
        (
            f"{len(pages)} pages. Mots alphabétiques hors du lexique (médiane), "
            "pages où ils restent plus de la moitié, et mots lus (médiane). Un "
            "indice de lisibilité, sans référence : une page manuscrite bien lue "
            "garde des noms propres hors lexique."
        ),
        "",
        "| source | pages lues | hors lexique | pages > 50 % | mots lus |",
        "|---|---|---|---|---|",
    ]
    for source, lus in textes.items():
        mesures = [hors(t) for t in lus.values()]
        lignes_.append(
            f"| {source} | {len(lus)} | {np.median([h for h, _ in mesures]):.0%} "
            f"| {sum(h > HORS_LEXIQUE for h, _ in mesures)} "
            f"| {np.median([n for _, n in mesures]):.0f} |"
        )
    texte = "\n".join(lignes_)
    args.pages.with_suffix(".md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "action", choices=("transcrire", "mesurer", "illisibles", "lexique")
    )
    parser.add_argument(
        "--pages", type=Path, help="liste de pages (fichier, page) au lieu de Chabin"
    )
    parser.add_argument("--nombre", type=int, default=100)
    parser.add_argument("--graine", type=int, default=2026)
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--modele", choices=list(MODELES))
    parser.add_argument("--url", default=URL)
    parser.add_argument(
        "--cle", type=Path, default=Path("data/anonymisation/vision/cle.txt")
    )
    parser.add_argument("--paralleles", type=int, default=8)
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument(
        "--alignement", type=Path, default=Path("data/chabin/alignement.csv")
    )
    parser.add_argument(
        "--typage",
        type=Path,
        default=Path("data/typage/departements/BnF_GDN_17_PDF.csv"),
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--sortie", type=Path, default=Path("data/ocr"))
    args = parser.parse_args()
    if args.action == "mesurer":
        mesurer(args)
    elif args.action == "illisibles":
        illisibles(args)
    elif args.action == "lexique":
        lexique(args)
    elif not args.modele:
        parser.error("--modele est requis")
    else:
        transcrire(args)


if __name__ == "__main__":
    main()
