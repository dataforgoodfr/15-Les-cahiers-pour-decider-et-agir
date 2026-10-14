"""Charge les contributions de l'édition de Marie-Anne Chabin (#37).

Lit l'extraction de ses transcriptions (`cahiers_chabin-extraction.json`,
sortie d'`extraction/chabin`) et `chabin/alignement.csv` (sortie de
`python -m chabin` dans `analyse/`), qui retrouve dans l'OCR des scans BnF
le début des contributions dactylographiées et des courriels. Seules
celles-là sont chargées : un manuscrit n'a pas de position dans le scan.
Elles forment un run de délimitation « édition Chabin », avec leur texte
anonymisé par l'édition, et gardent leur rang dans l'édition.

La fin est le début de la contribution suivante de l'édition, si elle est
retrouvée plus loin dans le même scan ; sinon le bas de la page du début,
qui peut la sous-estimer. La commande peut être relancée : elle remplace
les contributions de ce run, sans toucher aux autres, et ne l'active pas.
"""

import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers.models import Contribution, Document, Run

LIBELLE = "Édition Chabin, contributions imprimées retrouvées dans l'OCR (#37)"


def _debut(ligne: dict) -> tuple[int, float]:
    return int(ligne["page"]), float(ligne["y0"])


class Command(BaseCommand):
    help = "Charge les contributions imprimées de l'édition Chabin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyse",
            dest="data",
            type=Path,
            default=settings.BASE_DIR.parent / "analyse" / "data",
            help="dossier des sorties d'analyse/ (défaut : ../analyse/data)",
        )
        parser.add_argument(
            "--extraction",
            type=Path,
            default=settings.BASE_DIR.parent
            / "data"
            / "cahiers_chabin-extraction.json",
            help="sortie d'extraction/chabin (défaut : ../data/cahiers_chabin-extraction.json)",
        )

    @transaction.atomic
    def handle(self, *args, data: Path, extraction: Path, **options):
        chemin = data / "chabin" / "alignement.csv"
        if not chemin.is_file():
            raise CommandError(f"pas de {chemin} : lancer python -m chabin")
        if not extraction.is_file():
            raise CommandError(f"pas de {extraction} : lancer extraction/chabin")
        textes = {
            e["city"]["insee"]: [c["text"] for c in e["contributions"]]
            for e in json.loads(extraction.read_text(encoding="utf-8"))
            if e
        }
        with chemin.open(encoding="utf-8", newline="") as f:
            alignement = {(x["insee"], int(x["rang"])): x for x in csv.DictReader(f)}
        retrouvees = {k: x for k, x in alignement.items() if x["fichier"]}
        ids = dict(
            Document.objects.filter(
                fichier__in={x["fichier"] for x in retrouvees.values()}
            ).values_list("fichier", "id")
        )
        if retrouvees and not ids:
            raise CommandError("aucun document chargé : lancer charger_corpus")

        run, _ = Run.objects.get_or_create(
            genre=Run.Genre.DELIMITATION,
            libelle=LIBELLE,
            defaults={
                "auteur": "Marie-Anne Chabin, alignée par analyse/chabin",
                "notes": (
                    "Contributions dactylographiées et courriels de l'édition, "
                    "dont le début est retrouvé dans l'OCR du scan ; rang de "
                    "l'édition. La fin est le début suivant s'il est retrouvé "
                    "plus loin dans le même scan, sinon le bas de la page du "
                    "début."
                ),
            },
        )
        run.contributions.all().delete()
        contributions = []
        for (insee, rang), x in sorted(retrouvees.items()):
            if x["fichier"] not in ids:
                continue
            page, y = _debut(x)
            page_fin, y_fin = page, None
            suivante = retrouvees.get((insee, rang + 1))
            if (
                suivante
                and suivante["fichier"] == x["fichier"]
                and _debut(suivante) > (page, y)
            ):
                page_fin, y_fin = _debut(suivante)
            contributions.append(
                Contribution(
                    run=run,
                    document_id=ids[x["fichier"]],
                    rang=rang,
                    page_debut=page,
                    y_debut=y,
                    page_fin=page_fin,
                    y_fin=y_fin,
                    origine=f"édition Chabin ({x['genre']})",
                    texte=textes[insee][rang - 1],
                )
            )
        Contribution.objects.bulk_create(contributions)

        absents = sorted({x["fichier"] for x in retrouvees.values()} - set(ids))
        self.stdout.write(
            f"{len(contributions)} contributions dans "
            f"{len({c.document_id for c in contributions})} documents, sur "
            f"{len(alignement)} de l'édition alignées "
            f"({len(alignement) - len(retrouvees)} sans position), "
            f"run « {run} »."
        )
        if absents:
            self.stdout.write(
                f"Documents absents, contributions ignorées : {', '.join(absents)}"
            )
