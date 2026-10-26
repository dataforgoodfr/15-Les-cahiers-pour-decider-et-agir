"""Charge le découpage automatique de tous les cahiers citoyens (#5).

Lit `decoupage/corpus/contributions.csv` (sortie de `python -m decoupage.corpus`
dans `analyse/`) : les contributions trouvées par les règles et le modèle sur
les pages imprimées, arrêtées avant les pages manuscrites. Elles forment un
run de délimitation jamais activé : la plateforme continue de servir la
délimitation à la main ; celui-ci sert à comparer et à préparer la relecture.
La commande peut être relancée : elle remplace les contributions de ce run,
sans toucher aux autres. Les documents doivent être chargés avant
(`charger_corpus`).
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers.models import Contribution, Document, Run

from .charger_contributions import _nombre

LIBELLE = "Découpage automatique, règles et modèle, pages imprimées (#5)"


class Command(BaseCommand):
    help = "Charge le découpage automatique de tous les cahiers citoyens."

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
        chemin = data / "decoupage" / "corpus" / "contributions.csv"
        if not chemin.is_file():
            raise CommandError(f"pas de {chemin} : lancer python -m decoupage.corpus")
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f))
        fichiers = {x["fichier"] for x in lignes}
        ids = dict(
            Document.objects.filter(fichier__in=fichiers).values_list("fichier", "id")
        )
        if fichiers and not ids:
            raise CommandError("aucun document chargé : lancer charger_corpus")

        run, _ = Run.objects.get_or_create(
            genre=Run.Genre.DELIMITATION,
            libelle=LIBELLE,
            defaults={
                "auteur": "analyse/decoupage",
                "modele": "règles et régression logistique (decoupage.contributions)",
                "notes": (
                    "Pages imprimées seules ; une contribution s'arrête avant la "
                    "première page manuscrite, qui reste sans contribution. Non "
                    "modéré, sans extrait : jamais montré."
                ),
            },
        )
        run.contributions.all().delete()
        contributions = Contribution.objects.bulk_create(
            (
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
                    origine=x["regle"],
                    publiable=x["publiable"] == "1",
                )
                for x in lignes
                if x["fichier"] in ids
            ),
            batch_size=5000,
        )

        absents = len(fichiers - set(ids))
        self.stdout.write(
            f"{len(contributions)} contributions dans "
            f"{len({c.document_id for c in contributions})} documents, "
            f"run « {run} »{' actif' if run.actif else ''}."
        )
        if absents:
            self.stdout.write(
                f"{absents} documents absents de la base, contributions ignorées."
            )
