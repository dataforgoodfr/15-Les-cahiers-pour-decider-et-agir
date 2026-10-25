"""Charge les contributions délimitées à la main dans `analyse/` (#95).

Lit `delimitation/contributions.csv` (sortie de `python -m decoupage.delimitation`) :
toutes les contributions des cahiers du tirage délimités dans l'outil
d'annotation. Elles forment un run de délimitation « à la main », l'étalon
du découpage automatique. La commande peut être relancée : elle remplace les
contributions de ce run, sans toucher aux autres. Les documents et leurs
pages doivent être chargés avant (`charger_corpus`).
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers.models import Contribution, Document, Run

LIBELLE = "Délimitation à la main du tirage pour l'association (#21)"


def _nombre(valeur: str) -> float | None:
    return float(valeur) if valeur else None


class Command(BaseCommand):
    help = "Charge les contributions délimitées à la main dans analyse/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyse",
            dest="data",
            type=Path,
            default=settings.BASE_DIR.parent / "analyse" / "data",
            help="dossier des sorties d'analyse/ (défaut : ../analyse/data)",
        )

    @transaction.atomic
    def handle(self, *args, data: Path, **options):
        chemin = data / "delimitation" / "contributions.csv"
        if not chemin.is_file():
            raise CommandError(f"pas de {chemin} : lancer python -m decoupage.delimitation")
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f))
        ids = dict(
            Document.objects.filter(
                fichier__in={x["fichier"] for x in lignes}
            ).values_list("fichier", "id")
        )
        absents = sorted({x["fichier"] for x in lignes} - set(ids))
        if absents and len(absents) == len({x["fichier"] for x in lignes}):
            raise CommandError("aucun document chargé : lancer charger_corpus")

        run, cree = Run.objects.get_or_create(
            genre=Run.Genre.DELIMITATION,
            libelle=LIBELLE,
            defaults={
                "auteur": "outil d'annotation d'analyse/",
                "notes": (
                    "Débuts et fins notés à la main ; une fin non notée est "
                    "le début suivant, ou le bas de la dernière page."
                ),
            },
        )
        if (
            cree
            and not Run.objects.filter(
                genre=Run.Genre.DELIMITATION, actif=True
            ).exists()
        ):
            run.actif = True
            run.save(update_fields=["actif"])
        run.contributions.all().delete()
        contributions = Contribution.objects.bulk_create(
            Contribution(
                run=run,
                document_id=ids[x["fichier"]],
                rang=int(x["rang"]),
                page_debut=int(x["page_debut"]),
                x_debut=_nombre(x["x_debut"]),
                y_debut=_nombre(x["y_debut"]),
                page_fin=int(x["page_fin"]),
                x_fin=_nombre(x["x_fin"]),
                y_fin=_nombre(x["y_fin"]),
                origine="annotation",
                publiable=x["publiable"] == "1",
            )
            for x in lignes
            if x["fichier"] in ids
        )

        publiables = sum(c.publiable for c in contributions)
        self.stdout.write(
            f"{len(contributions)} contributions dans "
            f"{len({c.document_id for c in contributions})} documents "
            f"({len(contributions) - publiables} non publiables), "
            f"run « {run} »{' actif' if run.actif else ''}."
        )
        if absents:
            self.stdout.write(
                f"Documents absents, contributions ignorées : {', '.join(absents)}"
            )
