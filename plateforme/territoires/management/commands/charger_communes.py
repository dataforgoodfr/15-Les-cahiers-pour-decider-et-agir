"""Charge régions, départements et communes depuis geo.api.gouv.fr.

La commande peut être relancée : elle met à jour ce qui existe déjà.
"""

import json
import urllib.request

from django.core.management.base import BaseCommand
from django.db import transaction

from territoires.models import CODE_INCONNU, Commune, Departement, Region

API = "https://geo.api.gouv.fr"
CHAMPS = "code,nom,codeDepartement,codesPostaux,population,centre,codeParent"


def lire(chemin):
    with urllib.request.urlopen(API + chemin, timeout=60) as reponse:
        return json.load(reponse)


class Command(BaseCommand):
    help = "Charge le découpage administratif depuis geo.api.gouv.fr."

    @transaction.atomic
    def handle(self, *args, **options):
        regions = {r["code"]: r["nom"] for r in lire("/regions")}
        departements = {d["code"]: d for d in lire("/departements")}
        communes = lire(f"/communes?fields={CHAMPS}")
        arrondissements = lire(
            f"/communes?type=arrondissement-municipal&fields={CHAMPS}"
        )

        # Les collectivités d'outre-mer (Saint-Pierre-et-Miquelon, Polynésie…)
        # ont des communes, mais ne figurent pas dans la liste des départements.
        for code in {c["codeDepartement"] for c in communes} - departements.keys():
            departements[code] = lire(f"/departements/{code}")
            regions.setdefault(code, departements[code]["nom"])

        for code, nom in regions.items():
            Region.objects.update_or_create(code=code, defaults={"nom": nom})
        region_par_code = {r.code: r for r in Region.objects.all()}
        for d in departements.values():
            Departement.objects.update_or_create(
                code=d["code"],
                defaults={"nom": d["nom"], "region": region_par_code[d["codeRegion"]]},
            )
        departement_par_code = {d.code: d for d in Departement.objects.all()}

        def commune(c, parente=None):
            longitude, latitude = c.get("centre", {}).get("coordinates", (None, None))
            return Commune(
                code_insee=c["code"],
                nom=c["nom"],
                departement=departement_par_code[c["codeDepartement"]],
                codes_postaux=c.get("codesPostaux", []),
                population=c.get("population"),
                latitude=latitude,
                longitude=longitude,
                commune_parente_id=parente,
            )

        enregistrer(commune(c) for c in communes)
        parentes = dict(Commune.objects.values_list("code_insee", "id"))
        enregistrer(
            (commune(a, parentes[a["codeParent"]]) for a in arrondissements),
            ["commune_parente"],
        )

        region, _ = Region.objects.get_or_create(
            code="99", defaults={"nom": "Étranger ou inconnu"}
        )
        departement, _ = Departement.objects.get_or_create(
            code="999", defaults={"nom": "Étranger ou inconnu", "region": region}
        )
        Commune.objects.get_or_create(
            code_insee=CODE_INCONNU,
            defaults={"nom": "Étranger ou inconnu", "departement": departement},
        )

        self.stdout.write(
            f"{Region.objects.count()} régions, {Departement.objects.count()} "
            f"départements, {Commune.objects.count()} communes."
        )


def enregistrer(communes, champs_en_plus=()):
    Commune.objects.bulk_create(
        communes,
        batch_size=2000,
        update_conflicts=True,
        unique_fields=["code_insee"],
        update_fields=[
            "nom",
            "departement",
            "codes_postaux",
            "population",
            "latitude",
            "longitude",
            *champs_en_plus,
        ],
    )
