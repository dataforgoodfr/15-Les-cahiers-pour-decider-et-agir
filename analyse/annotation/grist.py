"""Tâches « sous-thèmes » et « paires » dans un tableur Grist (#252, #253).

    uv run python -m annotation.grist preparer [--revue data/themes/revue.csv]
        [--paires data/paires/paires.csv] [--sortie data/grist]
    uv run python -m annotation.grist reverser {themes,paires} EXPORT.csv
        --annotateur NOM [--journal data/annotation/<tâche>.jsonl]

Pour les bénévoles qui n'installent rien : chacun annote sa propre copie
d'un document Grist, sans voir les réponses des autres. `preparer` écrit les
tables à importer, une ligne par proposition ou par paire, et la liste des
choix à coller dans la colonne de réponse. Les paires perdent leur lot, leur
tranche et leur similarité : l'annotateur ne doit pas les voir.

Les choix portent un code en tête (`S07 · RIC`, `2 · même sujet, mesure
différente`) : des sous-thèmes contiennent des virgules, et le code se relit
quel que soit le format d'export de Grist. `reverser` lit l'export CSV d'une
copie et ajoute ses réponses au journal de l'outil d'annotation, que lisent
`classement.themes.accord` et `classement.paires.accord`. Une ligne sans
réponse est sautée ; relancer sur un export plus récent ajoute les nouvelles
réponses, et la dernière l'emporte.
"""

import argparse
import csv
import re
from pathlib import Path

from annotation.paires import JUGEMENTS, Journal, lire_paires
from annotation.themes import NOMS, JournalThemes

AUCUN = "S00 · aucun sous-thème"
CHOIX_THEMES = [AUCUN] + [f"S{i:02d} · {nom}" for i, nom in enumerate(NOMS, 1)]
CHOIX_PAIRES = [f"{i} · {j}" for i, j in enumerate(JUGEMENTS, 1)]
VRAI = {"true", "1", "oui", "vrai", "x", "yes"}


def preparer_themes(revue: Path) -> list[dict]:
    with revue.open(encoding="utf-8", newline="") as f:
        return [
            {
                "proposition": x["proposition"],
                "contribution": x["contribution"],
                "commune": x["commune"],
                "numero": x["numero"],
                "contexte": x["contexte"],
                "texte": x["texte"],
                "sous_themes": "",
                "mal_coupee": "",
            }
            for x in csv.DictReader(f)
        ]


def preparer_paires(paires: Path) -> list[dict]:
    return [
        {
            "paire": p["paire"],
            "a_contexte": p["a"]["contexte"],
            "a_texte": p["a"]["texte"],
            "b_contexte": p["b"]["contexte"],
            "b_texte": p["b"]["texte"],
            "jugement": "",
        }
        for p in lire_paires(paires)
    ]


def sous_themes(cellule: str) -> list[str] | None:
    """Les sous-thèmes cochés, [] pour « aucun », None si rien n'est coché."""
    codes = {int(c) for c in re.findall(r"\bS(\d{2})\b", cellule)}
    if not codes:
        return None
    if not codes <= set(range(len(CHOIX_THEMES))):
        raise ValueError(f"code de sous-thème inconnu : {cellule!r}")
    return sorted(NOMS[c - 1] for c in codes if c)


def jugement(cellule: str) -> str | None:
    m = re.match(r"\s*(\d)\s*·", cellule)
    if not m:
        return None
    i = int(m.group(1))
    if not 1 <= i <= len(JUGEMENTS):
        raise ValueError(f"jugement inconnu : {cellule!r}")
    return JUGEMENTS[i - 1]


def reverser_themes(lignes: list[dict], journal: JournalThemes, annotateur: str) -> int:
    n = 0
    for x in lignes:
        mal_coupee = x.get("mal_coupee", "").strip().lower() in VRAI
        choisis = sous_themes(x.get("sous_themes", ""))
        if choisis is None and not mal_coupee:
            continue
        journal.annoter(x["proposition"], annotateur, choisis or [], mal_coupee)
        n += 1
    return n


def reverser_paires(lignes: list[dict], journal: Journal, annotateur: str) -> int:
    n = 0
    for x in lignes:
        j = jugement(x.get("jugement", ""))
        if j is not None:
            journal.juger(x["paire"], annotateur, j)
            n += 1
    return n


def _ecrire(chemin: Path, lignes: list[dict]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("preparer")
    p.add_argument("--revue", type=Path, default=Path("data/themes/revue.csv"))
    p.add_argument("--paires", type=Path, default=Path("data/paires/paires.csv"))
    p.add_argument("--sortie", type=Path, default=Path("data/grist"))
    r = sous.add_parser("reverser")
    r.add_argument("tache", choices=["themes", "paires"])
    r.add_argument("export", type=Path)
    r.add_argument("--annotateur", required=True)
    r.add_argument("--journal", type=Path)
    args = parser.parse_args()

    if args.commande == "preparer":
        args.sortie.mkdir(parents=True, exist_ok=True)
        themes = preparer_themes(args.revue)
        paires = preparer_paires(args.paires)
        _ecrire(args.sortie / "themes.csv", themes)
        _ecrire(args.sortie / "paires.csv", paires)
        (args.sortie / "choix-sous-themes.txt").write_text(
            "\n".join(CHOIX_THEMES) + "\n"
        )
        (args.sortie / "choix-paires.txt").write_text("\n".join(CHOIX_PAIRES) + "\n")
        print(
            f"{len(themes)} propositions, {len(paires)} paires, "
            f"{len(CHOIX_THEMES)} choix de sous-thèmes dans {args.sortie}"
        )
        return

    with args.export.open(encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    if args.tache == "themes":
        chemin = args.journal or Path("data/annotation/themes.jsonl")
        n = reverser_themes(lignes, JournalThemes(chemin), args.annotateur)
    else:
        chemin = args.journal or Path("data/annotation/paires.jsonl")
        n = reverser_paires(lignes, Journal(chemin), args.annotateur)
    print(
        f"{n} réponses de {args.annotateur} ajoutées à {chemin}, sur {len(lignes)} lignes"
    )


if __name__ == "__main__":
    main()
