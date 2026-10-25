"""Débuts de contributions trouvés par un modèle de vision, contre la délimitation à la main (#5).

    uv run python -m decoupage.vision preparer --sortie data/decoupage/vision/reglage
        [--nombre 10] [--graine 2026] [--pages-max 40]
    uv run python -m decoupage.vision preparer --sortie data/decoupage/vision/test
        --nombre 25 --exclure data/decoupage/vision/reglage
    (lecture par le modèle : voir plus bas)
    uv run python -m decoupage.vision mesurer --sortie data/decoupage/vision/test

Les cahiers délimités à la main (`panels.selection`) sont caviardés : leurs
pages peuvent être montrées à un modèle hébergé. `preparer` tire des cahiers
d'au plus `--pages-max` pages écrites, et rend chaque page écrite (hors pages
« à écarter ») caviardée comme les exports (notes à cacher et repérages
relus), dans le sens de lecture qualifié dans l'outil d'annotation, avec une
règle rouge graduée de 0 (haut) à 100 (bas) dans la marge. Il écrit
`pages.csv`, `reference.csv` (les débuts notés à la main, dans le repère de la
page affichée) et `lots.csv` : des lots d'au plus `PAGES_PAR_LOT` pages, un
par sous-agent. `--exclure` écarte les cahiers d'un tirage précédent : la
consigne a été réglée sur le premier (`reglage`), on la mesure sur un autre
(`test`).

**Lecture** : pour chaque lot, un sous-agent Claude Code sur le modèle
`MODELE` reçoit `CONSIGNE` (ses dossiers, et son dossier de sortie
`sorties/<lot>/`) ; il écrit, par cahier, une ligne par page :
`<image> : aucun`, ou les graduations des débuts (`<image> : 12, 58`). Un
dossier par lot : des agents qui écrivent dans les mêmes fichiers se
marchent dessus.

`mesurer` compare ces débuts à la référence avec la mesure du découpage
(`decoupage.contributions.regles.evaluer`), par type de page, et, sur les pages
dactylographiées et mixtes, à la chaîne actuelle (`data/contributions/debuts.csv`).
Aussi à la page : une page ouvre-t-elle au moins une contribution ?

Les pages restent dans `data/` ; la sortie ne donne que des comptes.
"""

import argparse
import csv
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from annotation.carnet import Carnet
from anonymisation.masquage import CHAMPS, a_masquer, fusionner
from decoupage.contributions.regles import evaluer
from panels.selection.__main__ import A_CACHER, cadre

MODELE = "claude-haiku-5-5"
DEBUT = "début de contribution"
ECARTER = "à écarter"
VIERGE = "vierge"
IMPRIMEES = {"dactylographiée", "mixte"}
DPI = 110
MARGE = 60  # pixels de la règle, à gauche de la page
PAGES_PAR_LOT = 45
NON_VUE = "[IMAGE NON VUE]"
CONSIGNE = """\
Tu aides à mesurer le découpage de cahiers de doléances (2019) en \
contributions. Les images sont déjà anonymisées : les rectangles noirs sont \
des parties cachées (souvent un nom, une signature, une adresse).

Traite UNIQUEMENT les dossiers ci-dessous, l'un après l'autre. N'ouvre, ne lis \
et n'écris aucun autre dossier ni aucun autre fichier que ceux indiqués ici.
{dossiers}
Dans chaque dossier, les images sont les pages écrites du cahier, dans \
l'ordre de leur nom (001_…, 002_…). Une règle rouge graduée de 0 (haut de la \
page) à 100 (bas) est dessinée dans la marge gauche.

Une contribution est un texte d'un même auteur, ou d'un même groupe, d'un \
seul tenant : une lettre, un courriel imprimé, un formulaire rempli, une \
liste de propositions d'une même personne, un compte rendu de réunion. Elle \
peut tenir sur plusieurs pages ; une page peut en contenir plusieurs. Ne sont \
PAS des contributions : la couverture ou la page de titre du cahier, une page \
d'ouverture imprimée par la mairie ou une association de maires, un \
intercalaire. Une contribution qui continue sur la page suivante ne commence \
pas sur cette page-là.

Attention aux pages écrites à la main : dans un cahier, un registre ou un \
formulaire, plusieurs personnes écrivent souvent à la suite sur la même page, \
et chaque intervention est une contribution distincte. Indices d'un nouveau \
début : un changement d'écriture, d'encre ou de stylo ; une signature, une \
date ou un rectangle noir (nom caché) qui clôt l'intervention précédente ; un \
trait, un espace, une date ou une nouvelle formule (« Je », « Monsieur le \
Maire », « Bonjour ») qui ouvre la suivante. Cherche-les sur chaque page \
manuscrite, et note chaque début. En revanche, une même personne qui numérote \
ses propositions, dans la même écriture, reste une seule contribution.

Pour chaque dossier, traite les images UNE PAR UNE, dans l'ordre :
1. Lis l'image avec l'outil Read, en gardant en tête la page précédente du \
même cahier.
2. Repère chaque endroit où une NOUVELLE contribution commence sur cette \
page, et lis sur la règle rouge la graduation (de 0 à 100) de son tout \
premier élément : en-tête, logo ou titre d'un formulaire, date ou formule \
d'appel d'une lettre, en-tête d'un courriel, ou première ligne.
3. Ajoute aussitôt une ligne au fichier {sortie}/<nom du dossier>.txt avec \
Bash (echo '…' >> fichier ; crée le dossier s'il n'existe pas), de la forme :
   <nom de l'image> : aucun
   ou
   <nom de l'image> : 12, 58
   (les graduations des débuts, du haut vers le bas). Si l'image ne \
s'affiche pas ou que tu ne la vois pas vraiment, écris : <nom de l'image> : \
[IMAGE NON VUE]. Ne prétends jamais avoir vu une page que tu n'as pas vue.

Ne recopie aucun texte des pages, ni dans les fichiers ni dans ta réponse. \
Réponds seulement : le nombre de pages traitées par dossier, les pages non \
vues, et les difficultés rencontrées.
"""
LIGNE = re.compile(r"\s*\d+_p(\d+)\.jpg\s*:\s*(.*)")


def types_des_pages(typage: Path, fichiers: set[str], qualifications: dict) -> dict:
    """Par page des cahiers : son type (vérifié dans l'outil, sinon typage), ou
    `ECARTER` ; les pages de service sont laissées de côté."""
    types = {}
    for f in sorted(typage.glob("*.csv")):
        with f.open(encoding="utf-8", newline="") as g:
            for ligne in csv.DictReader(g):
                if ligne["fichier"] in fichiers and ligne["page_de_service"] == "0":
                    types[ligne["fichier"], int(ligne["page"])] = ligne["type_page"]
    for cle, q in qualifications.items():
        if cle not in types:
            continue
        if q["problemes"].get(ECARTER):
            types[cle] = ECARTER
        elif q["type"]:
            types[cle] = q["type"]
    return types


def vers_affichage(page: pymupdf.Page, rotation: int) -> pymupdf.Matrix:
    """Du repère des notes (rotation du PDF comprise) au repère de la page
    tournée de `rotation` degrés, comme dans l'outil. Tourne la page."""
    avant = page.derotation_matrix
    page.set_rotation((page.rotation + rotation) % 360)
    return avant * page.rotation_matrix


def haut(rect: pymupdf.Rect, matrice: pymupdf.Matrix) -> float:
    return min(
        (pymupdf.Point(x, y) * matrice).y
        for x in (rect.x0, rect.x1)
        for y in (rect.y0, rect.y1)
    )


def avec_regle(pix: pymupdf.Pixmap) -> pymupdf.Document:
    img = pymupdf.open()
    largeur, hauteur = pix.width + MARGE, pix.height
    page = img.new_page(width=largeur, height=hauteur)
    page.insert_image(pymupdf.Rect(MARGE, 0, largeur, hauteur), pixmap=pix)
    rouge = (1, 0, 0)
    for pct in range(0, 101, 5):
        y = min(hauteur - 2, max(2, pct / 100 * hauteur))
        page.draw_line(
            (0, y),
            (MARGE - 5 if pct % 10 == 0 else MARGE / 2, y),
            color=rouge,
            width=1.5,
        )
        if pct % 10 == 0:
            page.insert_text(
                (2, y + (12 if pct == 0 else -3)), str(pct), fontsize=13, color=rouge
            )
    return img


def lots(
    cahiers: list[tuple[str, int]], taille: int = PAGES_PAR_LOT
) -> list[list[str]]:
    """Range les cahiers (nom, pages) en lots d'au plus `taille` pages, les plus
    gros d'abord ; un cahier plus gros qu'un lot en forme un à lui seul."""
    sortie: list[tuple[int, list[str]]] = []
    for nom, n in sorted(cahiers, key=lambda c: -c[1]):
        for k, (total, noms) in enumerate(sortie):
            if total + n <= taille:
                sortie[k] = (total + n, [*noms, nom])
                break
        else:
            sortie.append((n, [nom]))
    return [noms for _, noms in sortie]


def preparer(args) -> None:
    with (args.selection / "selection.csv").open(encoding="utf-8", newline="") as f:
        cahiers = [x["fichier"] for x in csv.DictReader(f) if x["statut"] == "exporté"]
    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    types = types_des_pages(args.typage, set(cahiers), qualifications)
    ecrites = defaultdict(list)
    for (f, n), t in types.items():
        if t != VIERGE:
            ecrites[f].append(n)
    exclus = set()
    for dossier in args.exclure:
        with (dossier / "pages.csv").open(encoding="utf-8", newline="") as f:
            exclus |= {x["fichier"] for x in csv.DictReader(f)}
    candidats = [
        f for f in cahiers if f not in exclus and 4 <= len(ecrites[f]) <= args.pages_max
    ]
    tires = random.Random(args.graine).sample(
        candidats, min(args.nombre, len(candidats))
    )
    notes, _ = carnet.etat()
    par_cahier = defaultdict(list)
    for n in notes.values():
        if n.get("fichier") in tires:
            par_cahier[n["fichier"]].append(n)
    with (args.selection / "reperes.csv").open(encoding="utf-8", newline="") as f:
        reperes = [
            {**r, "page": int(r["page"]), **{k: float(r[k]) for k in CHAMPS}}
            for r in csv.DictReader(f)
            if r["fichier"] in tires
        ]
    retablis = list(carnet.retablis().values())
    chemins = {p.name: p for p in args.versement.rglob("CC_*.pdf") if p.name in tires}
    pages, reference, tailles = [], [], []
    for f in tires:
        dossier = args.sortie / "cahiers" / Path(f).stem
        dossier.mkdir(parents=True, exist_ok=True)
        ns = par_cahier[f]
        a_cacher = [
            {**n, **dict(zip(CHAMPS, cadre(n), strict=True))}
            for n in ns
            if n["etiquette"] in A_CACHER
        ]
        masques = a_masquer(
            fusionner([r for r in reperes if r["fichier"] == f]),
            [r for r in retablis if r["fichier"] == f],
            a_cacher,
        )
        noirs = defaultdict(list)
        for m in masques:
            noirs[m["page"]].append(cadre(m))
        lues = [n for n in sorted(ecrites[f]) if types[f, n] != ECARTER]
        with pymupdf.open(chemins[f]) as doc:
            for rang, n in enumerate(lues, 1):
                page = doc[n - 1]
                vers_pdf = page.derotation_matrix
                for r in noirs.get(n, []):
                    # une donnée sur un pixel de bord reste cachée : marge d'un point
                    page.add_redact_annot(
                        (r + (-1, -1, 1, 1)) * vers_pdf, fill=(0, 0, 0)
                    )
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
                rotation = qualifications.get((f, n), {}).get("rotation") or 0
                matrice = vers_affichage(page, rotation)
                avec_regle(page.get_pixmap(dpi=DPI)).load_page(0).get_pixmap(
                    dpi=72
                ).save(dossier / f"{rang:03d}_p{n}.jpg", jpg_quality=80)
                pages.append(
                    {
                        "fichier": f,
                        "page": n,
                        "type": types[f, n],
                        "hauteur": round(page.rect.height, 2),
                        "matrice": " ".join(f"{v:.6g}" for v in matrice),
                    }
                )
                reference += [
                    {"fichier": f, "page": n, "y": round(haut(cadre(x), matrice), 2)}
                    for x in ns
                    if x["page"] == n and x["etiquette"] == DEBUT
                ]
        tailles.append((Path(f).stem, len(lues)))
    ecrire(args.sortie / "pages.csv", pages)
    ecrire(args.sortie / "reference.csv", reference, ["fichier", "page", "y"])
    lignes_lots = [
        {"lot": k, "cahier": nom}
        for k, noms in enumerate(lots(tailles), 1)
        for nom in noms
    ]
    ecrire(args.sortie / "lots.csv", lignes_lots)
    print(
        f"{len(tires)} cahiers, {len(pages)} pages "
        f"({dict(Counter(p['type'] for p in pages))}), {len(reference)} débuts notés, "
        f"{len({x['lot'] for x in lignes_lots})} lots, dans {args.sortie}"
    )


def ecrire(chemin: Path, lignes: list[dict], champs: list[str] | None = None) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs or list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)


def consigne(sortie: Path, lot: int) -> str:
    """La consigne d'un lot, ses dossiers et son dossier de sortie en clair."""
    with (sortie / "lots.csv").open(encoding="utf-8", newline="") as f:
        noms = [x["cahier"] for x in csv.DictReader(f) if int(x["lot"]) == lot]
    racine = sortie.resolve()
    dossiers = "\n".join(f"- {racine / 'cahiers' / nom}/" for nom in noms)
    return CONSIGNE.format(dossiers=dossiers, sortie=racine / "sorties" / str(lot))


def lire_sorties(dossier: Path, hauteurs: dict) -> tuple[list, set, int]:
    """Les débuts lus par le modèle (fichier, page, ordonnée en points dans le
    repère affiché), les pages vues, et le nombre de pages non vues."""
    debuts, vues, non_vues = [], set(), 0
    for chemin in sorted(dossier.rglob("*.txt")):
        fichier = chemin.stem + ".pdf"
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            m = LIGNE.match(ligne)
            if not m or (fichier, int(m[1])) not in hauteurs:
                continue
            cle = (fichier, int(m[1]))
            if NON_VUE in m[2]:
                non_vues += 1
                continue
            vues.add(cle)
            debuts += [
                (*cle, float(g.replace(",", ".")) / 100 * hauteurs[cle])
                for g in re.findall(r"\d+(?:[.,]\d+)?", m[2])
            ]
    return debuts, vues, non_vues


def mesure(predits: list, reference: list, ensemble: set) -> dict:
    ref = [r for r in reference if (r[0], r[1]) in ensemble]
    pr = [p for p in predits if (p[0], p[1]) in ensemble]
    precision, rappel = evaluer(pr, ref)
    pages_predites = {(p[0], p[1]) for p in pr}
    pages_ref = {(r[0], r[1]) for r in ref}
    commun = len(pages_predites & pages_ref)
    return {
        "pages": len(ensemble),
        "trouves": len(pr),
        "notes": len(ref),
        "precision": precision,
        "rappel": rappel,
        "precision_page": commun / len(pages_predites) if pages_predites else 0.0,
        "rappel_page": commun / len(pages_ref) if pages_ref else 0.0,
    }


def mesurer(args) -> None:
    with (args.sortie / "pages.csv").open(encoding="utf-8", newline="") as f:
        pages = list(csv.DictReader(f))
    hauteurs = {(p["fichier"], int(p["page"])): float(p["hauteur"]) for p in pages}
    matrices = {
        (p["fichier"], int(p["page"])): pymupdf.Matrix(
            *map(float, p["matrice"].split())
        )
        for p in pages
    }
    with (args.sortie / "reference.csv").open(encoding="utf-8", newline="") as f:
        reference = [
            (x["fichier"], int(x["page"]), float(x["y"])) for x in csv.DictReader(f)
        ]
    modele, vues, non_vues = lire_sorties(args.sortie / "sorties", hauteurs)
    # la chaîne actuelle, dans le même repère
    chaine = []
    with (args.contributions / "debuts.csv").open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            cle = (x["fichier"], int(x["page"]))
            if cle in matrices:
                r = pymupdf.Rect(*(float(x[k]) for k in ("x0", "y0", "x1", "y1")))
                chaine.append((*cle, haut(r, matrices[cle])))
    par_type = defaultdict(set)
    for p in pages:
        cle = (p["fichier"], int(p["page"]))
        if cle in vues:
            par_type[p["type"]].add(cle)
    imprimees = set().union(*(par_type[t] for t in IMPRIMEES))
    lignes = [
        {"ensemble": "toutes", "source": MODELE, **mesure(modele, reference, vues)},
        *(
            {"ensemble": t, "source": MODELE, **mesure(modele, reference, ens)}
            for t, ens in sorted(par_type.items())
        ),
        {
            "ensemble": "imprimées",
            "source": MODELE,
            **mesure(modele, reference, imprimees),
        },
        {
            "ensemble": "imprimées",
            "source": "règles et modèle",
            **mesure(chaine, reference, imprimees),
        },
    ]
    print(
        f"{len({p['fichier'] for p in pages})} cahiers, {len(pages)} pages ; "
        f"vues par le modèle : {len(vues)} ; non vues : {non_vues}"
    )
    for x in lignes:
        print(
            f"  {x['ensemble']:16s} {x['source']:18s} {x['trouves']:4d} débuts / {x['notes']:4d} notés"
            f" ({x['pages']} pages) : précision {x['precision']:.0%}, "
            f"rappel {x['rappel']:.0%} ; à la page {x['precision_page']:.0%}, {x['rappel_page']:.0%}"
        )
    ecrire(args.sortie / "mesure.csv", lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("preparer", "consigne", "mesurer"))
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/decoupage/vision/reglage")
    )
    parser.add_argument("--nombre", type=int, default=10)
    parser.add_argument("--graine", type=int, default=2026)
    parser.add_argument("--pages-max", type=int, default=40)
    parser.add_argument("--exclure", type=Path, nargs="*", default=[])
    parser.add_argument("--lot", type=int, help="consigne : le lot")
    parser.add_argument("--selection", type=Path, default=Path("data/selection"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--contributions", type=Path, default=Path("data/contributions")
    )
    args = parser.parse_args()
    if args.action == "preparer":
        preparer(args)
    elif args.action == "consigne":
        print(consigne(args.sortie, args.lot))
    else:
        mesurer(args)


if __name__ == "__main__":
    main()
