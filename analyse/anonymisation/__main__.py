"""Repérages de données personnelles à faire vérifier (issue #7).

    uv run python -m anonymisation [--cahiers data/tirage/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--debuts data/contributions/debuts.csv] [--annotation data/annotation]
        [--sortie data/anonymisation] [--modele ollama:qwen3.5:9b ...]
        [--seulement-vues]

Méthodes dans `anonymisation.detection`. Lit les pages dactylographiées des
cahiers, et les en-têtes de formulaire trouvés par `contributions`. Écrit :

- `reperes.csv` dans la sortie : une ligne par repérage (fichier, page,
  cadre en points PDF, étiquette, source) ;
- la liste « anonymisation-a-masquer » dans l'outil d'annotation : tous les
  repérages, fusionnés, en relecture inversée (`anonymisation.masquage`) :
  masqués par défaut, le relecteur rétablit les fausses alertes et encadre
  les oublis ;
- les zones de formulaire : les blocs posés à la main sur au moins deux
  exemplaires d'un formulaire, reportés sur les autres. Les exemplaires se
  reconnaissent à l'en-tête trouvé par `contributions`, ou à leurs lignes
  imprimées apprises sur les pages annotées (`detection.modele_appris`),
  y compris sur les pages remplies à la main ;
- `masques.csv` dans la sortie : ce qu'il faut masquer après relecture
  (repérages non rétablis, et oublis encadrés), l'entrée du caviardage.

`--modele` ajoute un modèle local (`anonymisation.modeles`) : un LLM servi par
Ollama (`ollama:qwen3.5:9b`) ou GLiNER (`gliner`). Ses réponses sont gardées
dans `modeles/` de la sortie. `--seulement-vues` ne lit que les pages déjà
vues dans l'outil d'annotation, pour comparer des modèles sans lire tout le tirage :
il mesure sans réécrire `reperes.csv` ni les listes des règles.

Deux mesures. Sur les pages relues à l'ancienne (tâche « anonymisation »,
repérages acceptés en notes), un repérage est juste s'il recouvre une donnée
annotée. Sur les pages relues en masquage (tâche « masquage »), un repérage
est juste s'il n'a pas été rétabli, et les notes sont les oublis. Des cadres
et des comptes, jamais de texte.
"""

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from anonymisation.detection import (
    CHEVAUCHEMENT,
    EXEMPLAIRES,
    charger_prenoms,
    modele_appris,
    mots_personnels,
    recouvrement,
    retirer_repandues,
    zones,
)
from anonymisation.masquage import a_masquer, fusionner, mesurer_relecture
from anonymisation.modeles import Cache, charger, localiser, texte_de_la_page
from communes import sources
from contributions.__main__ import pages_lues
from ouvertures.ouvertures import LONGUEUR_LIGNE, normaliser
from panel.panel import code_insee

COUVERTE = 0.9  # part d'une note recouverte par une zone pour être couverte
TACHE = "anonymisation"  # relecture à l'ancienne : accepter les repérages
RELECTURE = "masquage"  # relecture inversée : rétablir les fausses alertes
LISTE = "anonymisation-a-masquer"
ANCIENNES = ("anonymisation-mots", "anonymisation-zones", "anonymisation-modeles")
PRENOMS = "https://www.insee.fr/fr/statistiques/fichier/7633685/nat2022_csv.zip"

PERSONNELLES = {
    "nom",
    "prénom",
    "adresse",
    "courriel",
    "téléphone",
    "autre donnée identifiante",
    "bloc de coordonnées",
}
CHAMPS = ("x0", "y0", "x1", "y1")


def mots_de_la_page(page: pymupdf.Page) -> list[tuple]:
    """Les mots, cadres ramenés au repère de la page affichée."""
    sortie = []
    for x0, y0, x1, y1, *reste in page.get_text("words"):
        r = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
        sortie.append((r.x0, r.y0, r.x1, r.y1, *reste))
    return sortie


def lignes_placees(page: pymupdf.Page) -> dict[str, tuple[float, float]]:
    """Les lignes de la page, normalisées, et leur coin haut gauche dans le
    repère de la page affichée (la première, si une ligne revient)."""
    sortie = {}
    for bloc in page.get_text("dict")["blocks"]:
        for ligne in bloc.get("lines", []):
            x = normaliser("".join(s["text"] for s in ligne["spans"]))
            if len(x) > LONGUEUR_LIGNE and x not in sortie:
                r = pymupdf.Rect(ligne["bbox"]) * page.rotation_matrix
                sortie[x] = (r.x0, r.y0)
    return sortie


def modeles_appris(
    chemins: dict[str, Path], notes: list[dict], relues: set
) -> tuple[list[dict], dict[str, tuple[int, int, int]]]:
    """Zones des cahiers dont au moins deux pages portent des notes de
    données personnelles, reportées sur les exemplaires de leur formulaire.

    Le report ne touche que les pages sans note ni relecture : sur une page
    annotée ou relue, le lecteur a déjà dit ce qu'il fallait cacher. Rend
    aussi, par cahier où le report touche des pages, la validation croisée :
    (pages reportées, notes couvertes par les zones apprises sans leur page,
    notes)."""
    par_cahier = defaultdict(list)
    for n in notes:
        if n["fichier"] in chemins:
            par_cahier[n["fichier"]].append(n)
    reperes, validation = [], {}
    for fichier, annotees in sorted(par_cahier.items()):
        annotees_pages = {n["page"] for n in annotees}
        if len(annotees_pages) < EXEMPLAIRES:
            continue
        with pymupdf.open(chemins[fichier]) as doc:
            pages = {n + 1: lignes_placees(doc[n]) for n in range(doc.page_count)}
        reportes = modele_appris(pages, annotees)
        if not reportes:
            continue
        nouveaux = [
            {"fichier": fichier, **r}
            for r in reportes
            if r["page"] not in annotees_pages and (fichier, r["page"]) not in relues
        ]
        if not nouveaux:
            continue
        reperes += nouveaux
        couvertes = 0
        for p in annotees_pages:
            zones_p = [
                z
                for z in modele_appris(pages, [n for n in annotees if n["page"] != p])
                if z["page"] == p
            ]
            couvertes += sum(
                any(recouvrement(n, z) >= COUVERTE for z in zones_p)
                for n in annotees
                if n["page"] == p
            )
        pages_reportees = len({r["page"] for r in nouveaux})
        validation[fichier] = (pages_reportees, couvertes, len(annotees))
    return reperes, validation


def zones_reportees(debuts: list[dict], notes: list[dict]) -> list[dict]:
    """Zones de chaque cahier à formulaire, reportées sur ses exemplaires."""
    tetes = defaultdict(dict)  # fichier -> page -> (x0, y0) de l'en-tête
    for d in debuts:
        if d["regle"].startswith("gabarit"):
            tetes[d["fichier"]].setdefault(
                int(d["page"]), (float(d["x0"]), float(d["y0"]))
            )
    reperes = []
    for fichier, pages in tetes.items():
        relatifs = []
        for n in notes:
            if n["fichier"] == fichier and n["page"] in pages:
                x, y = pages[n["page"]]
                relatifs.append(
                    {
                        "x0": min(n["x0"], n["x1"]) - x,
                        "y0": min(n["y0"], n["y1"]) - y,
                        "x1": max(n["x0"], n["x1"]) - x,
                        "y1": max(n["y0"], n["y1"]) - y,
                        "etiquette": n["etiquette"],
                        "page": n["page"],
                    }
                )
        for zone in zones(relatifs):
            appris = {r["page"] for r in relatifs if recouvrement(r, zone) > 0}
            for page, (x, y) in sorted(pages.items()):
                reperes.append(
                    {
                        "fichier": fichier,
                        "page": page,
                        "x0": round(max(0.0, zone["x0"] + x), 1),
                        "y0": round(max(0.0, zone["y0"] + y), 1),
                        "x1": round(zone["x1"] + x, 1),
                        "y1": round(zone["y1"] + y, 1),
                        "etiquette": zone["etiquette"],
                        "source": "zone apprise" if page in appris else "zone",
                    }
                )
    return reperes


def ecrire_liste_a_masquer(dossier: Path, reperes: list[dict]):
    par_page = defaultdict(list)
    for r in reperes:
        par_page[r["fichier"], r["page"]].append(
            {k: r[k] for k in CHAMPS} | {"etiquette": r["etiquette"], "id": r["id"]}
        )
    listes.ecrire(
        dossier,
        LISTE,
        "Données personnelles à masquer (relecture inversée)",
        (
            "Chaque repérage est caché par défaut : dans le doute, on cache. "
            "Cliquer sur une fausse alerte pour la rétablir (un second clic la "
            "recache ; « m » montre ou cache les repérages). Encadrer les "
            "données oubliées d'une note de donnée personnelle, puis marquer "
            "la page vue (v)."
        ),
        [
            {
                "fichier": f,
                "page": p,
                "marques": m,
                "commentaire": f"{len(m)} repérages",
            }
            for (f, p), m in sorted(par_page.items())
        ],
        tache=RELECTURE,
        mode="masquer",
    )


def mesurer(
    titre: str,
    reperes: list[dict],
    notes: list[dict],
    vues: set,
    pages: set | None = None,
):
    """Précision et rappel sur `pages` (par défaut, les pages vues où il y a
    des repérages)."""
    reperes = [r for r in reperes if (r["fichier"], r["page"]) in vues]
    if pages is None:
        pages = {(r["fichier"], r["page"]) for r in reperes}
    if not pages:
        print(f"  {titre} : pas encore de page vue")
        return
    reference = [n for n in notes if (n["fichier"], n["page"]) in pages]

    def touche(a, b):
        return (
            a["fichier"] == b["fichier"]
            and a["page"] == b["page"]
            and (recouvrement(a, b) >= CHEVAUCHEMENT)
        )

    justes = sum(any(touche(r, n) for n in reference) for r in reperes)
    if not reperes:
        print(f"  {titre} : aucun repérage (sur {len(pages)} pages vues)")
        return
    trouvees = sum(any(touche(n, r) for r in reperes) for n in reference)
    print(
        f"  {titre} : précision {justes / len(reperes):.0%}, rappel "
        f"{trouvees / len(reference) if reference else 0:.0%} "
        f"(sur {len(pages)} pages vues)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--debuts", type=Path, default=Path("data/contributions/debuts.csv")
    )
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/anonymisation"))
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--modele", action="append", default=[])
    parser.add_argument("--seulement-vues", action="store_true")
    args = parser.parse_args()

    with args.cahiers.open(encoding="utf-8", newline="") as f:
        fichiers = {ligne["fichier"] for ligne in csv.DictReader(f)}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    lues = pages_lues(args.typage, fichiers)
    carnet = Carnet(args.annotation / "notes.jsonl")
    vues = {cle for cle, s in carnet.statuts(TACHE).items() if s == "vue"}
    if args.seulement_vues:
        lues = {
            f: [n for n in numeros if (f, n) in vues] for f, numeros in lues.items()
        }
        lues = {f: numeros for f, numeros in lues.items() if numeros}
    modeles = [charger(nom) for nom in args.modele]
    caches = {
        m.nom: Cache(
            args.sortie / "modeles" / f"{re.sub(r'[^\w.-]', '_', m.nom)}.jsonl"
        )
        for m in modeles
    }

    prenoms = frozenset(charger_prenoms(sources.telecharger(PRENOMS, args.cache)))
    with args.communes.open(encoding="utf-8", newline="") as f:
        noms = {
            ligne["code_insee"]: ligne["nom_2019"] or ligne["commune"]
            for ligne in csv.DictReader(f)
        }
    par_cahier = {}
    for fichier in sorted(lues):
        commune = noms.get(code_insee(fichier) or "", "")
        par_cahier[fichier] = []
        with pymupdf.open(chemins[fichier]) as doc:
            for n in lues[fichier]:
                page = mots_de_la_page(doc[n - 1])
                for r in mots_personnels(page, commune, prenoms):
                    par_cahier[fichier].append({"page": n, **r, "source": "mot"})
                texte = texte_de_la_page(page)
                for m in modeles:
                    passages = caches[m.nom].obtenir(fichier, n, m, texte)
                    for r in localiser(passages, page):
                        par_cahier[fichier].append({"page": n, **r, "source": m.nom})
    tous = retirer_repandues(par_cahier)
    mots = [r for r in tous if r["source"] == "mot"]
    par_modele = [r for r in tous if r["source"] != "mot"]
    lues_vues = {(f, n) for f, numeros in lues.items() for n in numeros} & vues

    notes = [
        {**n, **{k: v for k, v in zip(CHAMPS, _ordonner(n))}}
        for n in carnet.positions()
        if n["etiquette"] in PERSONNELLES
    ]
    with args.debuts.open(encoding="utf-8", newline="") as f:
        debuts = list(csv.DictReader(f))
    relues = {
        cle for cle, s in carnet.statuts(RELECTURE, exacte=True).items() if s == "vue"
    }
    apprises, validation = modeles_appris(chemins, notes, relues)
    reportees = zones_reportees(debuts, notes) + apprises
    fusionnes = fusionner(tous + reportees)
    retablis = list(carnet.retablis().values())

    dossier = args.annotation / "listes"
    # sur les seules pages vues, on mesure sans écraser les sorties complètes
    if not args.seulement_vues:
        args.sortie.mkdir(parents=True, exist_ok=True)
        with (args.sortie / "reperes.csv").open("w", encoding="utf-8", newline="") as f:
            ecrivain = csv.DictWriter(
                f, ["fichier", "page", *CHAMPS, "etiquette", "source"]
            )
            ecrivain.writeheader()
            ecrivain.writerows(tous + reportees)
        masques = a_masquer(fusionnes, retablis, notes)
        with (args.sortie / "masques.csv").open("w", encoding="utf-8", newline="") as f:
            ecrivain = csv.DictWriter(
                f, ["fichier", "page", *CHAMPS, "etiquette", "origine"]
            )
            ecrivain.writeheader()
            ecrivain.writerows({k: m[k] for k in ecrivain.fieldnames} for m in masques)
        ecrire_liste_a_masquer(dossier, fusionnes)
        for ancienne in ANCIENNES:
            (dossier / f"{ancienne}.json").unlink(missing_ok=True)

    par_source = defaultdict(int)
    for r in tous + reportees:
        par_source[r["etiquette"], r["source"]] += 1
    print(f"{len(lues)} cahiers lus")
    for (etiquette, source), n in sorted(par_source.items()):
        print(f"  {etiquette} ({source}) : {n}")
    # règles et modèles se comparent sur les mêmes pages : toutes les vues
    mesurer("règles", mots, notes, vues, lues_vues)
    for m in modeles:
        retenus = [r for r in par_modele if r["source"] == m.nom]
        mesurer(m.nom, retenus, notes, vues, lues_vues)
    if modeles:
        mesurer("règles et modèles", tous, notes, vues, lues_vues)
    mesurer(
        "zones reportées", [r for r in reportees if r["source"] == "zone"], notes, vues
    )
    for fichier, (pages, couvertes, total) in sorted(validation.items()):
        print(
            f"  modèle appris, {fichier} : {pages} pages reportées ; "
            f"{couvertes} notes sur {total} couvertes, apprises sans leur page"
        )
    print(f"Relecture inversée : {len(fusionnes)} repérages fusionnés à masquer")
    mesure = mesurer_relecture(fusionnes, retablis, notes, relues)
    if mesure is None:
        print("  pas encore de page relue")
    else:
        precision, rappel, n = mesure
        print(
            f"  précision {precision:.0%}, rappel {rappel:.0%} (sur {n} pages relues)"
        )


def _ordonner(n: dict) -> tuple:
    return (
        min(n["x0"], n["x1"]),
        min(n["y0"], n["y1"]),
        max(n["x0"], n["x1"]),
        max(n["y0"], n["y1"]),
    )


if __name__ == "__main__":
    main()
