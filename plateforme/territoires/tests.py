from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .models import CODE_INCONNU, Commune, Departement

# Réponses réduites de geo.api.gouv.fr.
REPONSES = {
    "/regions": [{"code": "93", "nom": "Provence-Alpes-Côte d'Azur"}],
    "/departements": [{"code": "13", "nom": "Bouches-du-Rhône", "codeRegion": "93"}],
    "/departements/975": {
        "code": "975",
        "nom": "Saint-Pierre-et-Miquelon",
        "codeRegion": "975",
    },
    "/communes": [
        {
            "code": "13055",
            "nom": "Marseille",
            "codeDepartement": "13",
            "codesPostaux": ["13001", "13002"],
            "population": 877215,
            "centre": {"type": "Point", "coordinates": [5.38, 43.28]},
        },
        {
            "code": "97502",
            "nom": "Saint-Pierre",
            "codeDepartement": "975",
            "codesPostaux": ["97500"],
            "population": 5194,
        },
    ],
    "/communes?type=arrondissement-municipal": [
        {
            "code": "13201",
            "nom": "Marseille 1er Arrondissement",
            "codeDepartement": "13",
            "codesPostaux": ["13001"],
            "codeParent": "13055",
        }
    ],
}


def lire(chemin):
    return REPONSES[chemin.split("fields=")[0].rstrip("?&")]


@patch("territoires.management.commands.charger_communes.lire", lire)
class ChargementTests(TestCase):
    def charger(self):
        call_command("charger_communes", stdout=StringIO())

    def test_communes_chargees(self):
        self.charger()
        marseille = Commune.objects.get(code_insee="13055")
        self.assertEqual(marseille.departement.region.code, "93")
        self.assertEqual(marseille.codes_postaux, ["13001", "13002"])
        self.assertEqual((marseille.latitude, marseille.longitude), (43.28, 5.38))

    def test_outre_mer_hors_departements(self):
        self.charger()
        saint_pierre = Commune.objects.get(code_insee="97502")
        self.assertEqual(saint_pierre.departement.nom, "Saint-Pierre-et-Miquelon")
        self.assertIsNone(saint_pierre.latitude)

    def test_arrondissement_rattache_a_sa_commune(self):
        self.charger()
        arrondissement = Commune.objects.get(code_insee="13201")
        self.assertEqual(arrondissement.commune_parente.code_insee, "13055")

    def test_commune_inconnue(self):
        self.charger()
        self.assertEqual(
            Commune.objects.get(code_insee=CODE_INCONNU).departement.code, "999"
        )

    def test_relancer_met_a_jour_sans_doublon(self):
        self.charger()
        Commune.objects.filter(code_insee="13055").update(nom="Ancien nom")
        self.charger()
        self.assertEqual(Commune.objects.get(code_insee="13055").nom, "Marseille")
        self.assertEqual(Commune.objects.count(), 4)
        self.assertEqual(Departement.objects.count(), 3)


@patch("territoires.management.commands.charger_communes.lire", lire)
class AdminTests(TestCase):
    def setUp(self):
        call_command("charger_communes", stdout=StringIO())
        self.client.force_login(User.objects.create_superuser("admin"))

    def test_recherche_par_code_postal(self):
        reponse = self.client.get("/admin/territoires/commune/", {"q": "13001"})
        self.assertContains(reponse, "Marseille 1er Arrondissement")
        self.assertContains(reponse, "13055")
        self.assertNotContains(reponse, "97502")
