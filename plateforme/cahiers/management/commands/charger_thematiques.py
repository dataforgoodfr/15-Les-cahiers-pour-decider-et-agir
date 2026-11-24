"""Charge la taxonomie de thématiques (thèmes et sous-thèmes) depuis un CSV.

En `LOCAL` et `STAGING`, charge par défaut le jeu d'essai
`cahiers/data/thematiques_mock.csv`. En `PROD`, l'option `--fichier` est
obligatoire afin d'éviter de charger par erreur le fichier mock.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from cahiers.chargement import (
    FICHIER_THEMATIQUES_MOCK,
    ErreurChargement,
    charger_thematiques,
)


class Command(BaseCommand):
    help = "Charge les thématiques (thèmes principaux et sous-thèmes) depuis un CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichier",
            type=Path,
            default=None,
            help=(
                "Chemin du fichier CSV des thématiques "
                "(obligatoire en PROD ; défaut en LOCAL/STAGING : "
                "cahiers/data/thematiques_mock.csv)."
            ),
        )
        parser.add_argument(
            "--ecraser-descriptions",
            action="store_true",
            help=(
                "Écrase les descriptions déjà renseignées en base par celles "
                "du CSV (par défaut, les descriptions existantes sont préservées)."
            ),
        )

    def handle(self, *args, fichier: Path | None, ecraser_descriptions: bool, **options):
        if fichier is None:
            if settings.ENV == "PROD":
                raise CommandError(
                    "En environnement PROD, l'option --fichier est obligatoire "
                    "(le fichier mock n'est pas chargé par défaut)."
                )
            fichier = FICHIER_THEMATIQUES_MOCK

        try:
            resultat = charger_thematiques(
                fichier,
                ecraser_descriptions=ecraser_descriptions,
            )
        except (ErreurChargement, ValidationError, IntegrityError) as exc:
            raise CommandError(str(exc)) from exc

        details = [
            f"{resultat.crees} créées",
            f"{resultat.mises_a_jour} mises à jour",
        ]
        if resultat.descriptions_preservees:
            details.append(
                f"{resultat.descriptions_preservees} descriptions existantes préservées"
            )
        if resultat.absentes_du_fichier:
            details.append(
                f"{resultat.absentes_du_fichier} thématiques en base absentes du fichier "
                "(conservées)"
            )

        self.stdout.write(
            f"Thématiques chargées depuis {fichier.name} : {', '.join(details)}."
        )
