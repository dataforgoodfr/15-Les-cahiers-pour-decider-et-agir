"""Pages manquantes des courriers et formulaires types (issue #43).

    uv run python -m manquantes <pdf ou dossier>... [--sortie data/manquantes]
        [--processus 4]

Les modèles s'apprennent sur l'ensemble des fichiers donnés : passer tout le
versement. Écrit dans la sortie :

- `modeles.json` : les lignes de chaque page de chaque modèle (texte de
  courriers types, qui reste dans data/ comme toute donnée des cahiers) ;
- `modeles.csv` : par modèle, ses pages et ses exemplaires par statut ;
- `exemplaires.csv` : les exemplaires partiels, avec leur statut (version ou
  incomplet), les pages du modèle qui manquent, la coupure de phrase qui le
  confirme et la page voisine illisible. Des numéros, jamais de texte.
"""

import argparse
import csv
import json
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from manquantes.lecture import (
    exemplaires_du_fichier,
    initialiser,
    lignes_du_fichier,
    pages_frequentes,
)
from manquantes.manquantes import (
    COMPLET_,
    FICHIERS_MIN,
    INCOMPLET,
    VERSION,
    classer,
    coupure,
    illisible,
    modele,
    regrouper,
    structurer,
)
from typage.__main__ import pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chemins", type=Path, nargs="+")
    parser.add_argument("--sortie", type=Path, default=Path("data/manquantes"))
    parser.add_argument("--processus", type=int, default=4)
    args = parser.parse_args()
    fichiers = pdfs(args.chemins)
    args.sortie.mkdir(parents=True, exist_ok=True)

    compte = Counter()
    with Pool(args.processus) as pool:
        for ls in pool.imap_unordered(lignes_du_fichier, fichiers, chunksize=20):
            compte.update(ls)
    frequentes = {ligne for ligne, n in compte.items() if n >= FICHIERS_MIN}
    del compte
    print(f"{len(frequentes)} lignes fréquentes")

    with Pool(args.processus, initialiser, ({"frequentes": frequentes},)) as pool:
        pages = dict(pool.imap_unordered(pages_frequentes, fichiers, chunksize=20))
    pages = {nom: ps for nom, ps in pages.items() if any(ps)}
    groupes = regrouper({nom: set().union(*ps) for nom, ps in pages.items()})
    structures = [structurer(g, pages) for g in groupes]
    structures = [s for s in structures if len(s) >= 2]
    modeles = [modele(i, s) for i, s in enumerate(structures)]
    del pages
    print(f"{len(groupes)} modèles, dont {len(modeles)} sur plusieurs pages")
    with (args.sortie / "modeles.json").open("w", encoding="utf-8") as f:
        json.dump([[sorted(ls) for ls in s] for s in structures], f, ensure_ascii=False)

    tous = []
    with Pool(args.processus, initialiser, ({"modeles": modeles},)) as pool:
        for es in pool.imap_unordered(exemplaires_du_fichier, fichiers, chunksize=20):
            tous += es
    pages_par_modele = {m.numero: len(m.pages) for m in modeles}

    statuts = Counter()
    with (args.sortie / "exemplaires.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "fichier",
                "modele",
                "pages",
                "pages_du_modele",
                "pages_trouvees",
                "statut",
                "pages_manquantes",
                "coupure",
                "voisine_illisible",
            ]
        )
        for e, statut, manquantes in classer(tous, pages_par_modele):
            statuts[(e.modele, statut)] += 1
            if statut == COMPLET_:
                continue
            ecrivain.writerow(
                [
                    e.fichier,
                    e.modele,
                    " ".join(f"p{p}" for p in e.pages),
                    pages_par_modele[e.modele],
                    " ".join(str(k + 1) for k in e.portees),
                    statut,
                    " ".join(str(k + 1) for k in manquantes),
                    int(statut == INCOMPLET and coupure(e, manquantes)),
                    int(statut == INCOMPLET and illisible(e, manquantes)),
                ]
            )

    with (args.sortie / "modeles.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["modele", "pages", "complets", "versions", "incomplets"])
        for m in modeles:
            ecrivain.writerow(
                [m.numero, len(m.pages)]
                + [statuts[(m.numero, s)] for s in (COMPLET_, VERSION, INCOMPLET)]
            )

    total = Counter()
    for (_, s), n in statuts.items():
        total[s] += n
    print(", ".join(f"{n} {s}" for s, n in total.most_common()))
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
