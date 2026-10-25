"""L'OCR du versement contre Claude Haiku, sur les contributions tirées (issue #12).

    uv run python -m ocr.tirage preparer [--nombre 10] [--graine 2026]
    (transcription par Haiku : voir plus bas)
    uv run python -m ocr.tirage mesurer
    uv run python -m ocr.tirage desaccords [--nombre 48]

`ocr.chabin` mesure ABBYY contre une transcription humaine, mais dans un seul
département. Les contributions tirées (`panels.tirage`) couvrent la France ;
leurs exports caviardés et relus (`panels.selection`) peuvent être lus par un
modèle hébergé. Sans transcription humaine, on prend pour référence la
lecture de Claude Haiku (`MODELE`), après avoir vérifié à l'œil qu'elle a
raison quand les deux lectures diffèrent (`desaccords`).

- `preparer` : pour les contributions tirées dont toutes les pages écrites
  sont dactylographiées ou mixtes (type vérifié dans l'outil d'annotation,
  sinon typage), hors pages « à écarter », rend chaque page de l'export en
  JPEG (`pages/`) et garde son texte ABBYY (`abbyy/`) : la rédaction des
  exports a retiré le texte sous les masques et hors de la contribution, les
  deux lectures voient la même zone. Avec `--nombre`, une contribution par
  département, au hasard, jusqu'à ce nombre.
- **Transcription** : un sous-agent Claude Code, sur le modèle `MODELE`,
  reçoit `CONSIGNE` (le dossier à la place de `{dossier}`) et écrit une
  transcription par page dans `haiku/`. Il lit les images une à une : au-delà
  d'une limite d'images par requête, un agent peut prétendre avoir lu une page
  qu'il n'a pas vue, d'où la marque `[IMAGE NON VUE]`, comptée à part.
- `mesurer` : par page, le désaccord des deux lectures, sans accents, mots
  coupés en fin de ligne recollés, la lecture à la main de Haiku retirée
  (ABBYY ne lit que l'imprimé). Par caractère, l'ordre de lecture compte :
  sur une page en colonnes, il peut tout changer. Par mot, sans l'ordre.
  Pages à part selon qu'elles portent de l'écriture à la main ou non.
  Écrit `mesure.csv` et `tirage.md` dans la sortie.
- `desaccords` : des désaccords courts (un ou deux mots), tirés au hasard
  sur les pages sans écriture à la main, en planches PNG (l'extrait de page,
  le mot d'ABBYY encadré) et dans `desaccords.csv`, dont la colonne
  `verdict` (haiku, abbyy, neutre, indécidable) se remplit à la main ;
  `mesurer` en fait le compte.

Tout reste dans `data/` : les transcriptions citent les contributions.
`tirage.md` ne donne que des taux et des comptes.
"""

import argparse
import csv
import random
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pymupdf

from annotation.carnet import Carnet
from ocr.chabin import normalisee, sans_accents

MODELE = "claude-haiku-5-5"
CONSIGNE = """\
Tu sers d'OCR de vérification. Dans le dossier {dossier}/pages/ se trouvent \
des images JPEG de pages de cahiers de doléances (2019), déjà anonymisées : \
les zones grises ou noires sont des parties cachées.

Liste les fichiers *.jpg du dossier (avec Bash `ls`), puis traite-les UN PAR \
UN, dans l'ordre :
1. Lis l'image avec l'outil Read.
2. Écris aussitôt sa transcription avec l'outil Write, dans le dossier \
{dossier}/haiku/, sous le même nom avec l'extension `.txt`. Passe ensuite à \
l'image suivante.

Consignes de transcription :
- Recopie le texte exactement comme il est écrit : mêmes mots, même \
orthographe (y compris les fautes), mêmes accents, majuscules et ponctuation. \
Ne corrige rien, ne reformule rien, ne résume rien, n'ajoute rien.
- Un retour à la ligne par ligne de la page, dans l'ordre de lecture \
(colonnes de gauche à droite).
- Le texte écrit à la main (pas imprimé) : entoure-le de [manuscrit] … \
[/manuscrit].
- Un mot illisible : [?]. N'invente jamais un mot que tu ne vois pas.
- Les zones grises ou noires : n'écris rien à leur place.
- Si une image ne s'affiche pas ou que tu ne la vois pas vraiment, écris \
exactement `[IMAGE NON VUE]` dans son fichier. C'est essentiel : ne prétends \
jamais avoir lu une page que tu n'as pas vue.

Ne cite aucun texte des pages dans ta réponse finale. Réponds seulement : le \
nombre de pages transcrites, la liste des pages marquées [IMAGE NON VUE], et \
tout problème rencontré.
"""

IMPRIMEES = {"dactylographiée", "mixte"}
VIERGE = "vierge"
ECARTER = "à écarter"
DPI = 150
QUALITE_JPEG = 85
NON_VUE = "[IMAGE NON VUE]"
MANUSCRIT = re.compile(r"\[manuscrit\].*?(\[/manuscrit\]|$)", re.DOTALL)
CROCHETS = re.compile(r"\[[^\]]*\]")  # [?], [/manuscrit], descriptions
COUPURE = re.compile(
    r"\xad\s*\n\s*"
)  # mot coupé en fin de ligne (trait conditionnel d'ABBYY)
MAIN_MIN = 50  # caractères lus à la main par Haiku pour compter la page « avec main »
VERDICTS = ("haiku", "abbyy", "neutre", "indécidable")
COURT = 2  # mots au plus d'un désaccord court ; au-delà, un écart d'ordre


def recoller(texte: str) -> str:
    return COUPURE.sub("", texte)


def lecture_haiku(brut: str) -> tuple[str, int]:
    """Le texte imprimé lu par Haiku, et la longueur de ce qu'il a lu à la main."""
    main = sum(
        len(normalisee(CROCHETS.sub(" ", m[0]))) for m in MANUSCRIT.finditer(brut)
    )
    return CROCHETS.sub(" ", MANUSCRIT.sub(" ", brut)), main


def levenshtein(a, b) -> int:
    if not a or not b:
        return max(len(a), len(b))
    codes = {s: k for k, s in enumerate(dict.fromkeys([*a, *b]))}
    x = np.array([codes[s] for s in a])
    y = np.array([codes[s] for s in b])
    colonnes = np.arange(len(y) + 1)
    ligne = colonnes.copy()
    for i, r in enumerate(x, start=1):
        precedente = ligne
        ligne = np.empty_like(precedente)
        ligne[0] = i
        ligne[1:] = np.minimum(precedente[:-1] + (y != r), precedente[1:] + 1)
        # insertion : ligne[j] = min(ligne[j], ligne[j-1] + 1), d'un trait
        ligne = np.minimum.accumulate(ligne - colonnes) + colonnes
    return int(ligne[-1])


def desaccord_sans_ordre(a: list[str], b: list[str]) -> int:
    """Les mots de l'une des lectures qui manquent à l'autre, dans les deux sens."""
    ca, cb = Counter(a), Counter(b)
    return sum((ca - cb).values()) + sum((cb - ca).values())


def comparer(haiku: str, abbyy: str) -> dict:
    h, a = sans_accents(recoller(haiku)), sans_accents(recoller(abbyy))
    return {
        "caracteres": len(h),
        "mots": len(h.split()),
        "ecart_caracteres": levenshtein(h, a),
        "ecart_mots": desaccord_sans_ordre(h.split(), a.split()),
    }


def types_des_pages(typage: Path, annotation: Path) -> dict[tuple[str, int], str]:
    types = {}
    for f in sorted(typage.glob("*.csv")):
        with f.open(encoding="utf-8", newline="") as g:
            for ligne in csv.DictReader(g):
                types[ligne["fichier"], int(ligne["page"])] = ligne["type_page"]
    for cle, q in (
        Carnet(annotation / "notes.jsonl").qualifications(remarques=False).items()
    ):
        if q["problemes"].get(ECARTER):
            types[cle] = ECARTER
        elif q["type"]:
            types[cle] = q["type"]
    return types


def preparer(args) -> None:
    types = types_des_pages(args.typage, args.annotation)
    with (args.selection / "selection.csv").open(encoding="utf-8", newline="") as f:
        exportes = [x for x in csv.DictReader(f) if x["statut"] == "exporté"]

    def pages(x):
        return [
            (p, types.get((x["fichier"], p), "?"))
            for p in range(int(x["page_debut"]), int(x["page_fin"]) + 1)
        ]

    retenues = [
        x
        for x in exportes
        if all(t in IMPRIMEES | {VIERGE, ECARTER} for _, t in pages(x))
        and any(t in IMPRIMEES for _, t in pages(x))
    ]
    if args.nombre:
        rng = random.Random(args.graine)
        par_departement = {}
        for x in rng.sample(retenues, len(retenues)):
            par_departement.setdefault(x["departement"], x)
        retenues = list(par_departement.values())[: args.nombre]
    (args.sortie / "pages").mkdir(parents=True, exist_ok=True)
    (args.sortie / "abbyy").mkdir(exist_ok=True)
    lignes = []
    for x in retenues:
        doc = pymupdf.open(args.selection / x["pdf"])
        for i, (p, t) in enumerate(pages(x)):
            if t not in IMPRIMEES:
                continue
            nom = f"{Path(x['fichier']).stem}_p{i + 1}"
            page = doc[i]
            page.get_pixmap(dpi=DPI).save(
                args.sortie / "pages" / f"{nom}.jpg", jpg_quality=QUALITE_JPEG
            )
            (args.sortie / "abbyy" / f"{nom}.txt").write_text(
                page.get_text(sort=True), encoding="utf-8"
            )
            lignes.append([nom, x["fichier"], p, x["departement"], t])
    with (args.sortie / "pages.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["page", "fichier", "page_cahier", "departement", "type"])
        w.writerows(lignes)
    print(
        f"{len(retenues)} contributions, {len(lignes)} pages "
        f"({dict(Counter(ligne[4] for ligne in lignes))}), "
        f"{len({ligne[3] for ligne in lignes})} départements, dans {args.sortie}"
    )
    print(f"Consigne pour le sous-agent ({MODELE}) :")
    print(CONSIGNE.format(dossier=args.sortie.resolve()))


def lire_pages(sortie: Path) -> list[dict]:
    with (sortie / "pages.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:.1f} %".replace(".", ",") if b else "–"


def mesurer(args) -> None:
    lignes, non_vues, manquantes = [], 0, 0
    for p in lire_pages(args.sortie):
        chemin = args.sortie / "haiku" / f"{p['page']}.txt"
        if not chemin.exists():
            manquantes += 1
            continue
        brut = chemin.read_text(encoding="utf-8")
        if NON_VUE in brut:
            non_vues += 1
            continue
        haiku, main = lecture_haiku(brut)
        abbyy = (args.sortie / "abbyy" / f"{p['page']}.txt").read_text(encoding="utf-8")
        lignes.append({**p, **comparer(haiku, abbyy), "main": main})
    with (args.sortie / "mesure.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]) if lignes else ["page"])
        w.writeheader()
        w.writerows(lignes)
    verdicts = Counter()
    if (args.sortie / "desaccords.csv").exists():
        with (args.sortie / "desaccords.csv").open(encoding="utf-8", newline="") as f:
            verdicts = Counter(x["verdict"] for x in csv.DictReader(f) if x["verdict"])
    texte = rapport(lignes, non_vues, manquantes, verdicts)
    (args.sortie / "tirage.md").write_text(texte, encoding="utf-8")
    print(texte)


def rapport(
    lignes: list[dict], non_vues: int, manquantes: int, verdicts: Counter
) -> str:
    def bloc(nom, ls):
        if not ls:
            return f"| {nom} | 0 | | | | |"
        taux = sorted(x["ecart_caracteres"] / max(x["caracteres"], 1) for x in ls)
        mots = sum(x["mots"] for x in ls)
        return (
            f"| {nom} | {len(ls)} | {mots} "
            f"| {pct(sum(x['ecart_mots'] for x in ls), 2 * mots)} "
            f"| {pct(taux[len(taux) // 2], 1)} "
            f"| {pct(sum(x['ecart_caracteres'] for x in ls), sum(x['caracteres'] for x in ls))} |"
        )

    sans_main = [x for x in lignes if x["main"] < MAIN_MIN]
    avec_main = [x for x in lignes if x["main"] >= MAIN_MIN]
    sortie = [
        "# L'OCR du versement contre Claude Haiku, sur les contributions tirées",
        "",
        (
            f"Référence : {MODELE}. Pages comparées : {len(lignes)} "
            f"({len({x['fichier'] for x in lignes})} contributions, "
            f"{len({x['departement'] for x in lignes})} départements) ; "
            f"non vues par le modèle : {non_vues} ; sans transcription : {manquantes}."
        ),
        "",
        (
            "Désaccord sans accents, mots coupés recollés. Par mot : sans l'ordre, "
            "rapporté aux mots des deux lectures. Par caractère : l'ordre de lecture compte."
        ),
        "",
        "| Pages | Pages | Mots | Désaccord par mot | Par caractère, médiane | Par caractère, total |",
        "|---|---|---|---|---|---|",
        bloc("Imprimé seul", sans_main),
        bloc("Avec écriture à la main", avec_main),
        bloc("Toutes", lignes),
    ]
    par_departement = defaultdict(list)
    for x in sans_main:
        par_departement[x["departement"]].append(x)
    sortie += ["", "Imprimé seul, par département :", ""]
    sortie += [
        "| Département | Pages | Mots | Désaccord par mot | Par caractère, médiane | Par caractère, total |"
    ]
    sortie += ["|---|---|---|---|---|---|"]
    sortie += [bloc(d, ls) for d, ls in sorted(par_departement.items())]
    if verdicts:
        total = sum(verdicts.values())
        sortie += [
            "",
            f"Désaccords courts vérifiés à l'œil : {total}. "
            + ", ".join(f"{v} {verdicts[v]}" for v in VERDICTS if verdicts[v]),
        ]
    return "\n".join(sortie) + "\n"


def jetons_abbyy(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]:
    """Les mots d'ABBYY normalisés, chacun avec son cadre ; un mot coupé en
    fin de ligne (trait conditionnel) est recollé, avec le cadre de sa première
    moitié."""
    jetons, coupe = [], None
    for x0, y0, x1, y1, mot, *_ in page.get_text("words", sort=True):
        cadre = pymupdf.Rect(x0, y0, x1, y1)
        if coupe:
            mot, cadre = coupe[0] + mot, coupe[1]
            coupe = None
        if mot.endswith("\xad") and len(mot) > 1:
            coupe = (mot[:-1], cadre)
            continue
        jetons += [(j, cadre) for j in sans_accents(mot).split()]
    return jetons


def desaccords(args) -> None:
    mesures = {}
    with (args.sortie / "mesure.csv").open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            mesures[x["page"]] = x
    cas = []
    for p in lire_pages(args.sortie):
        if p["page"] not in mesures or int(mesures[p["page"]]["main"]) >= MAIN_MIN:
            continue
        doc = pymupdf.open(args.selection / "pdf" / p["fichier"])
        page = doc[int(p["page"].rsplit("_p", 1)[1]) - 1]
        brut = (args.sortie / "haiku" / f"{p['page']}.txt").read_text(encoding="utf-8")
        haiku = sans_accents(recoller(lecture_haiku(brut)[0])).split()
        abbyy = jetons_abbyy(page)
        if not abbyy:
            continue
        mots = [j for j, _ in abbyy]
        appariement = SequenceMatcher(None, mots, haiku, autojunk=False)
        for op, i1, i2, j1, j2 in appariement.get_opcodes():
            if op == "equal" or max(i2 - i1, j2 - j1) > COURT:
                continue
            cadre = pymupdf.Rect(abbyy[min(i1, len(abbyy) - 1)][1])
            for _, r in abbyy[i1:i2]:
                cadre |= r
            cas.append((p, " ".join(mots[i1:i2]), " ".join(haiku[j1:j2]), cadre))
    rng = random.Random(args.graine)
    tires = rng.sample(cas, min(args.nombre or len(cas), len(cas)))
    with (args.sortie / "desaccords.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "page", "abbyy", "haiku", "verdict"])
        for k, (p, a, h, _) in enumerate(tires, 1):
            w.writerow([k, p["page"], a, h, ""])
    planches(tires, args.selection / "pdf", args.sortie)
    print(
        f"{len(cas)} désaccords courts, {len(tires)} tirés : {args.sortie / 'desaccords.csv'}"
    )


def planches(tires: list, pdf: Path, sortie: Path, par_planche: int = 8) -> None:
    hauteur, largeur = 110, 900
    doc = pymupdf.open()
    for k, (p, a, h, cadre) in enumerate(tires):
        if k % par_planche == 0:
            planche = doc.new_page(width=largeur, height=par_planche * hauteur)
        source = pymupdf.open(pdf / p["fichier"])
        page = source[int(p["page"].rsplit("_p", 1)[1]) - 1]
        zone = (cadre + (-120, -12, 120, 12)) & page.rect
        y = (k % par_planche) * hauteur
        planche.insert_text(
            (5, y + 14), f"{k + 1}. ABBYY : «{a}»   Haiku : «{h}»", fontsize=11
        )
        cible = pymupdf.Rect(5, y + 20, largeur - 5, y + hauteur - 5)
        planche.show_pdf_page(
            cible, source, page.number, clip=zone, keep_proportion=True
        )
        # l'extrait est centré dans sa case : le mot d'ABBYY, encadré au même endroit
        echelle = min(cible.width / zone.width, cible.height / zone.height)
        x0 = cible.x0 + (cible.width - zone.width * echelle) / 2
        y0 = cible.y0 + (cible.height - zone.height * echelle) / 2
        r = (cadre - (zone.x0, zone.y0, zone.x0, zone.y0)) * echelle + (x0, y0, x0, y0)
        planche.draw_rect(r, color=(1, 0, 0), width=1)
    for i, planche in enumerate(doc, 1):
        planche.get_pixmap(dpi=110).save(sortie / f"planche_{i}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("preparer", "mesurer", "desaccords"))
    parser.add_argument(
        "--nombre", type=int, help="contributions (preparer) ou désaccords"
    )
    parser.add_argument("--graine", type=int, default=2026)
    parser.add_argument("--selection", type=Path, default=Path("data/selection"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/ocr/tirage"))
    args = parser.parse_args()
    {"preparer": preparer, "mesurer": mesurer, "desaccords": desaccords}[args.action](
        args
    )


if __name__ == "__main__":
    main()
