"""Charge les extraits choisis des transcriptions de Marie-Anne Chabin.

Lit le fichier `cahiers_chabin_extraits.json` et enregistre de manière
idempotente et en masse (`bulk_create`) :
- le `Run` de délimitation correspondant,
- les objets `Document` associés à chaque cahier citoyen,
- les objets `Contribution` contenant le texte des transcriptions.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers.models import Contribution, Document, Run

LIBELLE = "Extraits choisis des transcriptions de Marie-Anne Chabin"
AUTEUR = "Marie-Anne Chabin"

CHAMPS_DOCUMENT = ["categorie", "code_insee", "code_postal"]
CHAMPS_CONTRIBUTION = ["texte", "page_debut", "page_fin"]


def extraire_code_postal(nom_fichier: str) -> str:
    """Extrait le code postal d'un nom de fichier PDF standardisé.

    Exemple : `"CC_17600_190225_17119_MD_00811.pdf"` -> `"17600"`.
    """
    morceau = nom_fichier.split("_")
    return morceau[1] if len(morceau) > 1 else ""


def extraire_rang(titre: str) -> int:
    """Extrait le rang numérique situé au début du titre d'une contribution.

    Exemple : `"7. Manuscrit, 6 lignes, 31 mots (homme)"` -> `7`.
    """
    return int(titre.split(".", maxsplit=1)[0].strip())


class Command(BaseCommand):
    help = "Charge les extraits choisis des transcriptions de Marie-Anne Chabin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichier",
            type=Path,
            default=settings.BASE_DIR
                    / "cahiers"
                    / "data"
                    / "cahiers_chabin_extraits.json",
            help=(
                "Chemin du fichier JSON des extraits Chabin "
                "(défaut : cahiers/data/cahiers_chabin_extraits.json)"
            ),
        )

    @transaction.atomic
    def handle(self, *args, fichier: Path, **options):
        if not fichier.is_file():
            raise CommandError(f"Fichier introuvable : {fichier}")

        entrees = json.loads(fichier.read_text(encoding="utf-8"))

        # 1. Récupération ou création idempotente du Run
        run, _ = Run.objects.update_or_create(
            genre=Run.Genre.DELIMITATION,
            libelle=LIBELLE,
            defaults={"auteur": AUTEUR},
        )

        # 2. Préparation et création en masse des documents
        documents = []
        for entree in entrees:
            nom_fichier = Path(entree["pdf_files"][0]).name
            documents.append(
                Document(
                    fichier=nom_fichier,
                    categorie=Document.Categorie.CAHIER,
                    code_insee=entree["city"]["insee"],
                    code_postal=extraire_code_postal(nom_fichier),
                )
            )

        Document.objects.bulk_create(
            documents,
            update_conflicts=True,
            unique_fields=["fichier"],
            update_fields=CHAMPS_DOCUMENT,
        )

        noms_fichiers = [doc.fichier for doc in documents]
        ids_documents = dict(
            Document.objects.filter(fichier__in=noms_fichiers).values_list(
                "fichier", "id"
            )
        )

        # 3. Préparation et création en masse des contributions
        contributions = []
        for entree in entrees:
            nom_fichier = Path(entree["pdf_files"][0]).name
            document_id = ids_documents[nom_fichier]
            for item in entree["contributions"]:
                contributions.append(
                    Contribution(
                        run=run,
                        document_id=document_id,
                        rang=extraire_rang(item["title"]),
                        texte=item["text"],
                        page_debut=0,
                        page_fin=0,
                    )
                )

        Contribution.objects.bulk_create(
            contributions,
            update_conflicts=True,
            unique_fields=["run", "document", "rang"],
            update_fields=CHAMPS_CONTRIBUTION,
        )

        self.stdout.write(
            f"{len(contributions)} contributions chargées dans "
            f"{len(documents)} documents, run « {run} »."
        )
