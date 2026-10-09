"""Charge le découpage administratif de 2019 depuis l'INSEE.

Les fichiers téléchargés sont gardés dans SOURCES_DIR. La commande peut être
relancée : elle met à jour ce qui existe déjà.
"""

from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from territoires import sources
from territoires.models import Commune, Departement, Region

CHAMPS = [
    "type",
    "nom",
    "departement",
    "commune_parente",
    "population",
    "latitude",
    "longitude",
    "code_courant",
    "nom_courant",
]


class Command(BaseCommand):
    help = "Charge régions, départements et communes au 1er janvier 2019."

    @transaction.atomic
    def handle(self, *args, **options):
        regions, departements, communes = sources.lire(settings.SOURCES_DIR)

        for code, nom in regions.items():
            Region.objects.update_or_create(code=code, defaults={"nom": nom})
        for code, (nom, region) in departements.items():
            Departement.objects.update_or_create(
                code=code, defaults={"nom": nom, "region_id": region or None}
            )

        def instance(c, parente=True):
            return Commune(
                code=c.code,
                type=c.type,
                nom=c.nom,
                departement_id=c.departement,
                commune_parente_id=(c.commune_parente or None) if parente else None,
                population=c.population,
                latitude=c.latitude,
                longitude=c.longitude,
                code_courant=c.code_courant,
                nom_courant=c.nom_courant,
            )

        # En deux temps, pour qu'une commune parente existe avant ses rattachées.
        for parente in (False, True):
            Commune.objects.bulk_create(
                [instance(c, parente) for c in communes.values()],
                batch_size=2000,
                update_conflicts=True,
                unique_fields=["code"],
                update_fields=CHAMPS,
            )

        types = Counter(c.type for c in communes.values())
        fusionnees = sum(
            1 for c in communes.values() if c.type == "COM" and c.code_courant != c.code
        )
        self.stdout.write(
            f"{len(regions)} régions, {len(departements)} départements, "
            f"{len(communes)} communes ({', '.join(f'{t} {n}' for t, n in types.most_common())}), "
            f"dont {fusionnees} communes fusionnées depuis."
        )
