"""Débuts de contributions trouvés par un modèle de vision, contre la délimitation à la main (#5).

    uv run python -m decoupage.vision preparer --sortie data/decoupage/vision/reglage
        [--nombre 10] [--graine 2026] [--pages-max 40]
    uv run python -m decoupage.vision preparer --sortie data/decoupage/vision/test
        --nombre 25 --exclure data/decoupage/vision/reglage
    (lecture par le modèle : voir plus bas)
    uv run python -m decoupage.vision interroger --sortie data/decoupage/vision/test
        --modele qwen3.8-27b [--url …] [--paralleles 8]
    uv run python -m decoupage.vision verifier --sortie data/decoupage/vision/test
    uv run python -m decoupage.vision mesurer --sortie data/decoupage/vision/test
        [--lecteur sorties-qwen3.8-27b-verifie]

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

`interroger` pose la même question à un modèle servi par vLLM hors de la
machine (`anonymisation.vision.MODELES`, carte louée en Europe, jointe par un
tunnel) : chaque page est envoyée avec la page précédente du cahier, pour le
contexte, et `CONSIGNE_PAGE` (la même définition d'une contribution) ; le
modèle répond `{"debuts": [12, 58]}`. Les pages sont indépendantes, donc
interrogées en parallèle ; une page déjà lue n'est pas redemandée. Les
réponses vont dans `sorties-<modèle>/`, au même format.

`verifier` repose une question fermée pour chaque début lu en haut de page
(sous la graduation `HAUT`) : avec la page précédente, le haut de la page
continue-t-il sa contribution ? Si oui, le début est retiré
(`sorties-<modèle>-verifie/`). Servi page à page, Qwen prend volontiers le
haut d'une page de suite pour un début ; le lui dire dans la consigne, ou le
laisser raisonner (il ne s'arrête plus), n'y change rien.

`mesurer` compare les débuts d'un lecteur (`--lecteur` : `sorties`, Haiku,
par défaut, ou `sorties-<modèle>`) à la référence avec la mesure du découpage
(`decoupage.contributions.regles.evaluer`), par type de page, et, sur les pages
dactylographiées et mixtes, à la chaîne actuelle (`data/contributions/debuts.csv`).
Aussi à la page : une page ouvre-t-elle au moins une contribution ?

Les pages restent dans `data/` ; la sortie ne donne que des comptes.
"""

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from pathlib import Path

import pymupdf

from annotation.carnet import Carnet
from anonymisation.masquage import CHAMPS, a_masquer, fusionner
from anonymisation.vision import MODELES, URL, interroger_modele
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
# la définition d'une contribution, la même pour tous les lecteurs
DEFINITION = CONSIGNE[
    CONSIGNE.index("Une contribution est") : CONSIGNE.index("Pour chaque dossier")
]
CONSIGNE_PAGE = (
    "Ces images sont des pages d'un cahier de doléances (2019), déjà "
    "anonymisées : les rectangles noirs sont des parties cachées. {contexte}"
    "La page à analyser porte une règle rouge graduée de 0 (haut de la page) "
    "à 100 (bas) dans sa marge gauche.\n\n"
    + DEFINITION
    + "Sur la page à analyser, repère chaque endroit où une NOUVELLE "
    "contribution commence (pas la suite de la page précédente), et lis sur "
    "la règle rouge la graduation (de 0 à 100) de son tout premier élément : "
    "en-tête, logo ou titre d'un formulaire, date ou formule d'appel d'une "
    "lettre, en-tête d'un courriel, ou première ligne.\n\n"
    'Réponds uniquement par un objet JSON : {{"debuts": [12, 58]}}, les '
    'graduations du haut vers le bas, ou {{"debuts": []}} si aucune '
    "contribution ne commence sur cette page. Ne recopie aucun texte."
)
CONTEXTE_AVANT = (
    "La première image est la page précédente du même cahier, pour le "
    "contexte seulement ; la seconde est la page à analyser. "
)
CONTEXTE_PREMIERE = "C'est la première page écrite du cahier. "
HAUT = 15  # graduation sous laquelle un début est « en haut de page »
QUESTION_SUITE = (
    "Ces deux images sont deux pages successives d'un cahier de doléances "
    "(2019), déjà anonymisées : les rectangles noirs sont des parties "
    "cachées. Le texte tout en haut de la seconde page continue-t-il la "
    "contribution (lettre, liste, texte, formulaire) du bas de la première "
    "page : même auteur, même écriture, ou texte qui se poursuit ? Ou "
    "commence-t-il une nouvelle contribution ? Réponds uniquement par un "
    'objet JSON : {"suite": true} ou {"suite": false}. Ne recopie aucun texte.'
)


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


def graduations(reponse: str) -> list[float]:
    """Les graduations de la réponse du modèle (à ne jamais afficher)."""
    reponse = re.sub(r"<think>.*?</think>", "", reponse, flags=re.DOTALL)
    debut, fin = reponse.find("{"), reponse.rfind("}")
    if debut < 0 or fin <= debut:
        raise ValueError("pas d'objet JSON")
    valeurs = json.loads(reponse[debut : fin + 1]).get("debuts")
    if not isinstance(valeurs, list):
        raise TypeError("pas de liste de débuts")
    return sorted(
        float(v) for v in valeurs if isinstance(v, int | float) and 0 <= v <= 100
    )


def interroger(args) -> None:
    m = MODELES[args.modele]
    cle = args.cle.read_text().strip()
    sorties = args.sortie / f"sorties-{args.modele}"
    sorties.mkdir(exist_ok=True)
    taches = []
    for dossier in sorted((args.sortie / "cahiers").iterdir()):
        deja = {}
        if (sorties / f"{dossier.name}.txt").exists():
            for ligne in (
                (sorties / f"{dossier.name}.txt")
                .read_text(encoding="utf-8")
                .splitlines()
            ):
                nom, _, reste = ligne.partition(" : ")
                if NON_VUE not in reste:
                    deja[nom] = ligne
        images = sorted(dossier.glob("*.jpg"))
        for k, image in enumerate(images):
            avant = images[k - 1] if k else None
            taches.append((dossier.name, image, avant, deja.get(image.name)))

    def lire(tache):
        cahier, image, avant, deja = tache
        if deja:
            return cahier, deja
        texte = CONSIGNE_PAGE.format(
            contexte=CONTEXTE_AVANT if avant else CONTEXTE_PREMIERE
        )
        try:
            reponse = interroger_modele(
                args.url,
                cle,
                args.modele,
                image.read_bytes(),
                texte,
                m["options"],
                max_tokens=512,
                format_image="jpeg",
                avant=(avant.read_bytes(),) if avant else (),
            )
            valeurs = graduations(reponse)
        # une page sans réponse, ou sans réponse lisible, compte comme non vue
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
            print(f"  {image.name} : {type(e).__name__}")
            return cahier, f"{image.name} : {NON_VUE}"
        texte_valeurs = ", ".join(f"{v:g}" for v in valeurs) or "aucun"
        return cahier, f"{image.name} : {texte_valeurs}"

    par_cahier = defaultdict(list)
    with ThreadPoolExecutor(args.paralleles) as pool:
        for k, (cahier, ligne) in enumerate(pool.map(lire, taches), 1):
            par_cahier[cahier].append(ligne)
            if k % 50 == 0:
                print(f"  {k}/{len(taches)} pages", flush=True)
    for cahier, lignes in par_cahier.items():
        (sorties / f"{cahier}.txt").write_text(
            "\n".join(sorted(lignes)) + "\n", encoding="utf-8"
        )
    non_vues = sum(NON_VUE in x for ls in par_cahier.values() for x in ls)
    print(f"{len(taches)} pages, {non_vues} sans réponse lisible, dans {sorties}")


def verifier(args) -> None:
    """Repose la question des débuts en haut de page : un modèle servi page à
    page prend volontiers le haut d'une page de suite pour un début. Lit
    `sorties-<modèle>/`, écrit `sorties-<modèle>-verifie/`."""
    m = MODELES[args.modele]
    cle = args.cle.read_text().strip()
    source = args.sortie / f"sorties-{args.modele}"
    sorties = args.sortie / f"sorties-{args.modele}-verifie"
    sorties.mkdir(exist_ok=True)
    taches = []
    for chemin in sorted(source.glob("*.txt")):
        images = sorted((args.sortie / "cahiers" / chemin.stem).glob("*.jpg"))
        precedentes = {b.name: a for a, b in pairwise(images)}
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            nom, _, reste = ligne.partition(" : ")
            taches.append((chemin.stem, nom, reste, precedentes.get(nom)))

    def lire(tache):
        cahier, nom, reste, avant = tache
        valeurs = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", reste)]
        if NON_VUE in reste or avant is None or not valeurs or valeurs[0] >= HAUT:
            return cahier, f"{nom} : {reste}", 0
        image = args.sortie / "cahiers" / cahier / nom
        try:
            reponse = interroger_modele(
                args.url,
                cle,
                args.modele,
                image.read_bytes(),
                QUESTION_SUITE,
                m["options"],
                max_tokens=64,
                format_image="jpeg",
                avant=(avant.read_bytes(),),
            )
        except OSError as e:  # sans réponse, le début reste
            print(f"  {nom} : {type(e).__name__}")
            return cahier, f"{nom} : {reste}", 0
        suite = re.search(r'"suite"\s*:\s*true', reponse) is not None
        if suite:
            valeurs = valeurs[1:]
        texte = ", ".join(f"{v:g}" for v in valeurs) or "aucun"
        return cahier, f"{nom} : {texte}", int(suite)

    par_cahier, retires = defaultdict(list), 0
    with ThreadPoolExecutor(args.paralleles) as pool:
        for cahier, ligne, retire in pool.map(lire, taches):
            par_cahier[cahier].append(ligne)
            retires += retire
    for cahier, lignes in par_cahier.items():
        (sorties / f"{cahier}.txt").write_text(
            "\n".join(sorted(lignes)) + "\n", encoding="utf-8"
        )
    print(f"{retires} débuts en haut de page jugés une suite, retirés : {sorties}")


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
    modele, vues, non_vues = lire_sorties(args.sortie / args.lecteur, hauteurs)
    source = (
        MODELE if args.lecteur == "sorties" else args.lecteur.removeprefix("sorties-")
    )
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
        {"ensemble": "toutes", "source": source, **mesure(modele, reference, vues)},
        *(
            {"ensemble": t, "source": source, **mesure(modele, reference, ens)}
            for t, ens in sorted(par_type.items())
        ),
        {
            "ensemble": "imprimées",
            "source": source,
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
    parser.add_argument(
        "action",
        choices=("preparer", "consigne", "interroger", "verifier", "mesurer"),
    )
    parser.add_argument("--modele", choices=list(MODELES), default="qwen3.8-27b")
    parser.add_argument("--url", default=URL)
    parser.add_argument(
        "--cle", type=Path, default=Path("data/anonymisation/vision/cle.txt")
    )
    parser.add_argument("--paralleles", type=int, default=8)
    parser.add_argument(
        "--lecteur", default="sorties", help="mesurer : dossier des réponses"
    )
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
    elif args.action == "interroger":
        interroger(args)
    elif args.action == "verifier":
        verifier(args)
    elif args.action == "consigne":
        print(consigne(args.sortie, args.lot))
    else:
        mesurer(args)


if __name__ == "__main__":
    main()
