"""Données personnelles encadrées sur l'image par un modèle de vision (#128).

    uv run python -m anonymisation.vision calibrer --modele qwen3.8-27b
    uv run python -m anonymisation.vision interroger --modele qwen3.8-27b
    uv run python -m anonymisation.vision mesurer

Les règles et le modèle de `anonymisation` lisent la couche texte : ils ne
voient presque rien de ce qui est écrit à la main, là où sont la plupart des
données (blocs de coordonnées, signatures). Cacher toute l'encre les couvre,
mais cache deux tiers de l'écriture d'un manuscrit. Un modèle de vision
regarde l'image : on lui demande d'encadrer chaque donnée personnelle, sans
la recopier.

Le modèle est servi hors de cette machine, par une API compatible OpenAI
(vLLM) sur une carte louée en Europe, jointe par un tunnel SSH (`--url`).
Les pages lui sont envoyées en image ; on ne garde de sa réponse que des
boîtes et des catégories, jamais de texte.

- `calibrer` : une page factice, aux fausses coordonnées placées à des
  endroits connus, vérifie l'ordre des axes et l'échelle des boîtes du
  modèle (recouvrement de chaque fausse donnée) ;
- `interroger` : les pages de l'étalon de l'Aude (`anonymisation.aude.etalon`), boîtes
  écrites en points dans `<sortie>/<modele>.csv`, une ligne par page dans
  `<sortie>/<modele>.pages.csv` (durée, erreur). Une page déjà interrogée
  est sautée : la passe reprend où elle s'est arrêtée ;
- `mesurer` : pour chaque modèle interrogé, par type de page, les masques
  des Archives couverts (80 % de leur encre sous une boîte, ou de leur aire
  s'ils n'ont presque pas d'encre), les pages où un masque reste visible,
  l'encre et l'aire hors masques cachées. Écrit `<sortie>/mesure.md`.

Le critère de couverture n'est pas tout à fait celui de `anonymisation.aude.mesure`
(tous les mots de la couche texte du masque, et 80 % de l'encre hors mots) :
sur un manuscrit, la couche texte n'a pas de sens, seule l'encre compte.

Des comptes, jamais de texte.
"""

import argparse
import base64
import csv
import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np
import pymupdf

from anonymisation.aude.mesure import TYPES, charger_etalon
from anonymisation.masquage import CHAMPS

URL = "http://127.0.0.1:8000/v1"
DPI = 150  # résolution des images envoyées
COUVERT = 0.8  # part de l'encre (ou de l'aire) d'un masque à cacher
PEU_D_ENCRE = 20  # pixels d'encre en deçà desquels un masque se juge à l'aire
ETIQUETTES = ("name", "signature", "address", "phone", "email", "other")
CONSIGNE = (
    "This is a scanned page from a French citizens' grievance book (2019). "
    "Find every piece of personal data on it, handwritten or typed: names of "
    "private persons (first or last names), signatures, postal addresses, phone "
    "numbers, email addresses, and anything else that identifies a private "
    "person. When unsure, include it. Do not include the names of public "
    "figures or institutions. Do not transcribe any text. Answer with a JSON "
    "list only, one object per item, with the keys {cles}. {coordonnees} The "
    'label is one of "name", "signature", "address", "phone", "email", '
    '"other". If there is nothing, answer [].'
)
# la forme native des boîtes de chaque famille de modèles : clé, ordre des
# coordonnées, échelle (1000 : coordonnées relatives, de 0 à 1000)
FORMATS = {
    "xyxy": {
        "cle": "bbox_2d",
        "ordre": ("x0", "y0", "x1", "y1"),
        "texte": (
            '"bbox_2d" is [x_min, y_min, x_max, y_max], relative to the image, '
            "from 0 to 1000."
        ),
    },
    "yxyx": {
        "cle": "box_2d",
        "ordre": ("y0", "x0", "y1", "x1"),
        "texte": (
            '"box_2d" is [y_min, x_min, y_max, x_max], relative to the image, '
            "from 0 to 1000."
        ),
    },
}
# modèles essayés : dépôt, forme des boîtes, options de vLLM
MODELES = {
    "qwen3.8-27b": {
        "depot": "Qwen/Qwen3.8-27B",
        "format": "xyxy",
        "options": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    "gemma-4-31b": {"depot": "google/gemma-4-31B-it", "format": "yxyx", "options": {}},
}
# fausses données de la page de calibrage : (étiquette, texte, cadre en points)
FACTICES = [
    ("name", "Jeanne Exemple-Fictive", (60, 90, 260, 108)),
    ("address", "12 rue Imaginaire, 99999 Nulle-Part", (330, 90, 560, 108)),
    ("phone", "Tél. 01 23 45 67 89", (60, 700, 200, 718)),
    ("email", "jeanne.fictive@exemple.invalid", (330, 700, 560, 718)),
    ("name", "Paul Inventé", (400, 780, 520, 798)),
]


def consigne(format_: str) -> str:
    f = FORMATS[format_]
    return CONSIGNE.format(cles=f'"{f["cle"]}" and "label"', coordonnees=f["texte"])


def image_png(page: pymupdf.Page, dpi: int = DPI) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")


def demander(
    url: str, cle: str, modele: str, png: bytes, format_: str, options: dict
) -> str:
    """La réponse du modèle (à ne jamais afficher : elle peut citer la page)."""
    return interroger_modele(url, cle, modele, png, consigne(format_), options)


def interroger_modele(
    url: str,
    cle: str,
    modele: str,
    png: bytes,
    texte: str | None,
    options: dict,
    max_tokens: int = 2048,
    format_image: str = "png",
) -> str:
    """La réponse d'un modèle servi par vLLM à une image et une consigne
    (`texte`, ou l'image seule). Elle peut citer la page : ne jamais
    l'afficher."""
    contenu = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{format_image};base64,"
                + base64.b64encode(png).decode()
            },
        }
    ]
    if texte:
        contenu.append({"type": "text", "text": texte})
    corps = {
        "model": modele,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": contenu}],
        **options,
    }
    requete = urllib.request.Request(
        f"{url}/chat/completions",
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cle}"},
    )
    with urllib.request.urlopen(requete, timeout=600) as r:
        return json.load(r)["choices"][0]["message"]["content"] or ""


def boites(reponse: str, format_: str, largeur: float, hauteur: float) -> list[dict]:
    """Les boîtes de la réponse, en points dans le repère de la page affichée.
    Seules les clés de la boîte et l'étiquette sont lues ; un objet mal formé
    est ignoré."""
    f = FORMATS[format_]
    reponse = re.sub(r"<think>.*?</think>", "", reponse, flags=re.DOTALL)
    debut, fin = reponse.find("["), reponse.rfind("]")
    if debut < 0 or fin <= debut:
        raise ValueError("pas de liste JSON")
    objets = json.loads(reponse[debut : fin + 1])
    sortie = []
    for o in objets if isinstance(objets, list) else []:
        valeurs = o.get(f["cle"]) if isinstance(o, dict) else None
        if not isinstance(valeurs, list) or len(valeurs) != 4:
            continue
        try:
            v = dict(zip(f["ordre"], (float(x) for x in valeurs), strict=True))
        except TypeError, ValueError:
            continue
        cadre = {
            "x0": min(v["x0"], v["x1"]) * largeur / 1000,
            "x1": max(v["x0"], v["x1"]) * largeur / 1000,
            "y0": min(v["y0"], v["y1"]) * hauteur / 1000,
            "y1": max(v["y0"], v["y1"]) * hauteur / 1000,
        }
        etiquette = o.get("label")
        cadre["etiquette"] = etiquette if etiquette in ETIQUETTES else "other"
        sortie.append(cadre)
    return sortie


def recouvrement(a: dict, b: dict) -> float:
    """Intersection sur union de deux cadres."""
    largeur = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    hauteur = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if largeur <= 0 or hauteur <= 0:
        return 0.0
    inter = largeur * hauteur

    def aire(r):
        return (r["x1"] - r["x0"]) * (r["y1"] - r["y0"])

    return inter / (aire(a) + aire(b) - inter)


def page_factice() -> pymupdf.Document:
    """Une page A4 de doléance inventée, avec des fausses données."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for _, texte, (x0, y0, _, _) in FACTICES:
        page.insert_text((x0, y0 + 13), texte, fontsize=12, fontname="cour")
    corps = (
        "Nous demandons le retour des services publics dans les campagnes, "
        "une fiscalité plus juste et la prise en compte du vote blanc."
    )
    page.insert_textbox(pymupdf.Rect(60, 200, 535, 600), corps * 4, fontsize=12)
    return doc


def calibrer(args, cle: str) -> None:
    m = MODELES[args.modele]
    doc = page_factice()
    page = doc[0]
    reponse = demander(
        args.url, cle, args.modele, image_png(page), m["format"], m["options"]
    )
    # la page est factice : sa réponse peut s'afficher
    print(reponse)
    trouvees = boites(reponse, m["format"], page.rect.width, page.rect.height)
    for etiquette, texte, _ in FACTICES:
        # le cadre du texte tel qu'il est écrit, plus serré que celui prévu
        r = page.search_for(texte)[0]
        cadre = {"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1}
        meilleur = max((recouvrement(cadre, b) for b in trouvees), default=0.0)
        print(f"{etiquette:8s} recouvrement {meilleur:.2f}")


def interroger(args, cle: str) -> None:
    m = MODELES[args.modele]
    etalon, _ = charger_etalon(args.etalon)
    fichiers = {f for f, _ in etalon}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    args.sortie.mkdir(parents=True, exist_ok=True)
    chemin_boites = args.sortie / f"{args.modele}.csv"
    chemin_pages = args.sortie / f"{args.modele}.pages.csv"
    faites = set()
    if chemin_pages.exists():
        with chemin_pages.open(encoding="utf-8", newline="") as f:
            faites = {(p["fichier"], int(p["page"])) for p in csv.DictReader(f)}
    nouveau = not chemin_boites.exists()
    with (
        chemin_boites.open("a", encoding="utf-8", newline="") as fb,
        chemin_pages.open("a", encoding="utf-8", newline="") as fp,
    ):
        ecrit_b = csv.DictWriter(fb, ["fichier", "page", *CHAMPS, "etiquette"])
        ecrit_p = csv.DictWriter(
            fp, ["fichier", "page", "boites", "secondes", "erreur"]
        )
        if nouveau:
            ecrit_b.writeheader()
        if not faites:
            ecrit_p.writeheader()
        restantes = sorted(set(etalon) - faites)

        def une_page(png, largeur, hauteur):
            debut, erreur, trouvees = time.monotonic(), "", []
            try:
                reponse = demander(
                    args.url, cle, args.modele, png, m["format"], m["options"]
                )
                trouvees = boites(reponse, m["format"], largeur, hauteur)
            except (ValueError, urllib.error.URLError, TimeoutError) as e:
                # le type de l'erreur seulement : son message peut citer la réponse
                erreur = type(e).__name__
            return trouvees, round(time.monotonic() - debut, 1), erreur

        # les pages se rendent ici (pymupdf n'est pas sûr entre fils), les
        # requêtes partent en parallèle : vLLM les traite par lots
        en_cours, k = {}, 0
        with ThreadPoolExecutor(args.paralleles) as pool:
            for cle_page in [*restantes, None]:
                if cle_page is not None:
                    fichier, n = cle_page
                    with pymupdf.open(chemins[fichier]) as doc:
                        page = doc[n - 1]
                        rendu = (image_png(page), page.rect.width, page.rect.height)
                    en_cours[pool.submit(une_page, *rendu)] = cle_page
                    if len(en_cours) < args.paralleles:
                        continue
                attendues = (
                    wait(en_cours, return_when=FIRST_COMPLETED)[0]
                    if cle_page is not None
                    else list(en_cours)
                )
                for futur in attendues:
                    fichier, n = en_cours.pop(futur)
                    trouvees, secondes, erreur = futur.result()
                    for b in trouvees:
                        ecrit_b.writerow(
                            {"fichier": fichier, "page": n}
                            | {c: round(b[c], 1) for c in CHAMPS}
                            | {"etiquette": b["etiquette"]}
                        )
                    ecrit_p.writerow(
                        {
                            "fichier": fichier,
                            "page": n,
                            "boites": len(trouvees),
                            "secondes": secondes,
                            "erreur": erreur,
                        }
                    )
                    fb.flush()
                    fp.flush()
                    k += 1
                    print(
                        f"{k}/{len(restantes)} : {len(trouvees)} boîtes"
                        + (f", {erreur}" if erreur else ""),
                        flush=True,
                    )


def cache(forme: tuple[int, int], cadres: list[dict]) -> np.ndarray:
    """Les pixels (un par point) sous les cadres."""
    masque = np.zeros(forme, dtype=bool)
    for c in cadres:
        x0, y0 = max(0, int(c["x0"])), max(0, int(c["y0"]))
        masque[y0 : int(c["y1"]) + 1, x0 : int(c["x1"]) + 1] = True
    return masque


def mesurer_page(gris: np.ndarray, masques: list[dict], trouvees: list[dict]) -> dict:
    """Masques couverts, encre et aire hors masques cachées, sur une page."""
    encre = gris < 128
    sous_masques, sous_boites = cache(gris.shape, masques), cache(gris.shape, trouvees)
    couverts = 0
    for m in masques:
        zone = cache(gris.shape, [m])
        a_cacher = zone & encre if (zone & encre).sum() >= PEU_D_ENCRE else zone
        couverts += (a_cacher & sous_boites).sum() >= COUVERT * a_cacher.sum()
    hors = ~sous_masques
    return {
        "masques": len(masques),
        "couverts": int(couverts),
        "encre": int((encre & hors).sum()),
        "encre_cachee": int((encre & hors & sous_boites).sum()),
        "aire": int(hors.sum()),
        "aire_cachee": int((hors & sous_boites).sum()),
    }


def lire_boites(chemin: Path) -> dict[tuple[str, int], list[dict]]:
    sortie = defaultdict(list)
    with chemin.open(encoding="utf-8", newline="") as f:
        for b in csv.DictReader(f):
            sortie[b["fichier"], int(b["page"])].append(
                {c: float(b[c]) for c in CHAMPS} | {"etiquette": b["etiquette"]}
            )
    return sortie


def pourcent(a: float, b: float) -> str:
    return f"{a / b:.0%}" if b else "–"


def mesurer(args) -> None:
    etalon, douteuses = charger_etalon(args.etalon)
    fichiers = {f for f, _ in etalon}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    gris = {}
    for fichier, n in etalon:
        with pymupdf.open(chemins[fichier]) as doc:
            pix = doc[n - 1].get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
            gris[fichier, n] = np.frombuffer(pix.samples, np.uint8).reshape(
                pix.h, pix.w
            )
    lignes = [
        "# Modèles de vision sur l'étalon de l'Aude",
        "",
        (
            f"{len(etalon)} pages BnF, {douteuses} écartées pour un masque au report "
            "douteux. Un masque est couvert si 80 % de son encre (de son aire, "
            "s'il n'en a presque pas) est sous une boîte du modèle."
        ),
    ]
    for chemin_pages in sorted(args.sortie.glob("*.pages.csv")):
        nom = chemin_pages.name.removesuffix(".pages.csv")
        with chemin_pages.open(encoding="utf-8", newline="") as f:
            pages = {(p["fichier"], int(p["page"])): p for p in csv.DictReader(f)}
        trouvees = lire_boites(args.sortie / f"{nom}.csv")
        lignes += [
            "",
            f"## {nom}",
            "",
            (
                "| pages | interrogées | en erreur | boîtes | masques couverts "
                "| pages où un masque reste visible | encre hors masques cachée "
                "| aire hors masques cachée | secondes par requête |"
            ),
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for type_page in TYPES:
            cles = [k for k, p in etalon.items() if p["type"] == type_page]
            faites = [k for k in cles if k in pages]
            total = defaultdict(int)
            visibles = avec_masques = 0
            for k in faites:
                r = mesurer_page(gris[k], etalon[k]["masques"], trouvees.get(k, []))
                for c, v in r.items():
                    total[c] += v
                avec_masques += bool(r["masques"])
                visibles += r["couverts"] < r["masques"]
            erreurs = sum(1 for k in faites if pages[k]["erreur"])
            secondes = [float(pages[k]["secondes"]) for k in faites]
            lignes.append(
                f"| {type_page}s | {len(faites)} sur {len(cles)} | {erreurs} "
                f"| {sum(len(trouvees.get(k, [])) for k in faites)} "
                f"| {pourcent(total['couverts'], total['masques'])} "
                f"({total['couverts']} sur {total['masques']}) "
                f"| {visibles} sur {avec_masques} "
                f"| {pourcent(total['encre_cachee'], total['encre'])} "
                f"| {pourcent(total['aire_cachee'], total['aire'])} "
                f"| {np.median(secondes) if secondes else 0:.0f} |"
            )
    texte = "\n".join(lignes)
    (args.sortie / "mesure.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("calibrer", "interroger", "mesurer"))
    parser.add_argument("--modele", choices=list(MODELES))
    parser.add_argument("--url", default=URL)
    parser.add_argument("--paralleles", type=int, default=8)
    parser.add_argument(
        "--cle", type=Path, default=Path("data/anonymisation/vision/cle.txt")
    )
    parser.add_argument("--etalon", type=Path, default=Path("data/aude"))
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/vision")
    )
    args = parser.parse_args()
    if args.action == "mesurer":
        mesurer(args)
        return
    if not args.modele:
        parser.error("--modele est requis")
    cle = args.cle.read_text(encoding="utf-8").strip()
    if args.action == "calibrer":
        calibrer(args, cle)
    else:
        interroger(args, cle)


if __name__ == "__main__":
    main()
