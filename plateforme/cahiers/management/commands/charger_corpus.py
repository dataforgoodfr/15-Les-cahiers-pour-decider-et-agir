"""Charge les documents et les pages mesurés par `analyse/`.

Les cahiers citoyens typés par `analyse/typage`, leurs pages (type, rotation,
page de service ou d'ouverture) et les rattachements à une autre commune. La
couche texte n'est pas chargée. La commande peut être relancée : elle met à
jour ce qui existe déjà, sans toucher aux couches des runs.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers import analyse, noms
from cahiers.models import Document, Page, Rattachement
from territoires.models import Commune

CHAMPS_DOCUMENT = [
    "categorie",
    "mode",
    "code_postal",
    "date_depot",
    "numero",
    "code_insee",
    "commune",
    "nombre_pages",
]
CHAMPS_PAGE = ["type", "rotation", "service", "ouverture"]


class Command(BaseCommand):
    help = "Charge les documents et les pages mesurés par analyse/."

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
        if not (data / "typage").is_dir():
            raise CommandError(f"pas de sorties du typage dans {data}")
        lues = analyse.pages(data)
        documents = []
        for fichier, pages in lues.items():
            document = noms.document(fichier)
            document.nombre_pages = len(pages)
            documents.append(document)
        Document.objects.bulk_create(
            documents,
            batch_size=2000,
            update_conflicts=True,
            unique_fields=["fichier"],
            update_fields=CHAMPS_DOCUMENT,
        )
        ids = dict(
            Document.objects.filter(fichier__in=lues).values_list("fichier", "id")
        )

        Page.objects.bulk_create(
            (
                Page(document_id=ids[fichier], numero=numero, **vars(lue))
                for fichier, pages in lues.items()
                for numero, lue in pages.items()
            ),
            batch_size=5000,
            update_conflicts=True,
            unique_fields=["document", "numero"],
            update_fields=CHAMPS_PAGE,
        )

        Rattachement.objects.filter(document_id__in=ids.values()).delete()
        communes = set(Commune.objects.values_list("code", flat=True))
        rattachements = [
            Rattachement(
                document_id=ids[fichier],
                page_debut=page,
                code_insee=code,
                commune_id=code if code in communes else None,
            )
            for fichier, debuts in analyse.rattachements(data).items()
            if fichier in ids
            for page, code in debuts
        ]
        Rattachement.objects.bulk_create(rattachements)

        self.stdout.write(
            f"{len(ids)} documents, "
            f"{sum(len(p) for p in lues.values())} pages, "
            f"{len(rattachements)} rattachements à une autre commune."
        )
