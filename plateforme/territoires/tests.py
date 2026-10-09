from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from . import sources
from .models import Commune


def cog(typecom, com, dep="", comparent="", libelle=""):
    return {
        "typecom": typecom,
        "com": com,
        "dep": dep,
        "comparent": comparent,
        "libelle": libelle or com,
    }


def mouvement(av, ap, date, typecom_ap="COM"):
    return {"COM_AV": av, "COM_AP": ap, "DATE_EFF": date, "TYPECOM_AP": typecom_ap}


class Communes2019Tests(SimpleTestCase):
    def test_la_commune_de_plein_exercice_l_emporte(self):
        communes = sources.communes_2019(
            [cog("COMD", "01015", comparent="01015"), cog("COM", "01015", "01")]
        )
        self.assertEqual(communes["01015"].type, "COM")
        self.assertEqual(communes["01015"].commune_parente, "")

    def test_une_rattachee_prend_le_departement_de_sa_parente(self):
        communes = sources.communes_2019(
            [cog("COM", "01033", "01"), cog("COMD", "01205", comparent="01033")]
        )
        self.assertEqual(communes["01205"].departement, "01")
        self.assertEqual(communes["01205"].commune_parente, "01033")

    def test_collectivites_d_outre_mer(self):
        communes = sources.collectivites_outre_mer(
            [{"CODCOL": "975", "CODCOM": "502", "COM": "Saint-Pierre", "PMUN": "5406"}]
        )
        self.assertEqual(communes["97502"].departement, "975")
        self.assertEqual(communes["97502"].population, 5406)


class PassageTests(SimpleTestCase):
    def suivre(self, communes, mouvements, courant=("01138",)):
        communes = {c.code: c for c in communes}
        courant = [{"TYPECOM": "COM", "COM": c, "LIBELLE": c} for c in courant]
        sources.passage(communes, courant, mouvements)
        return communes

    def test_commune_fusionnee_depuis_2019(self):
        beon = sources.Commune("01039", "COM", "Béon", "01")
        self.suivre([beon], [mouvement("01039", "01138", "2023-01-01")])
        self.assertEqual(beon.code_courant, "01138")

    def test_chaine_de_mouvements(self):
        commune = sources.Commune("01001", "COM", "A", "01")
        self.suivre(
            [commune],
            [
                mouvement("01001", "01002", "2020-01-01"),
                mouvement("01002", "01138", "2024-01-01"),
            ],
        )
        self.assertEqual(commune.code_courant, "01138")

    def test_mouvement_anterieur_au_pivot_ignore(self):
        commune = sources.Commune("01001", "COM", "A", "01")
        self.suivre([commune], [mouvement("01001", "01138", "2018-01-01")])
        self.assertEqual(commune.code_courant, "")

    def test_une_deleguee_suit_sa_parente(self):
        deleguee = sources.Commune("01205", "COMD", "Lancrans", "01", "01033")
        self.suivre([deleguee], [], courant=["01033"])
        self.assertEqual(deleguee.code_courant, "01033")


class ChargementTests(TestCase):
    regions = {"84": "Auvergne-Rhône-Alpes"}
    departements = {"01": ("Ain", "84"), "975": ("Saint-Pierre-et-Miquelon", "")}

    def charger(self, communes):
        lire = (self.regions, self.departements, {c.code: c for c in communes})
        with patch.object(sources, "lire", return_value=lire):
            call_command("charger_communes", stdout=StringIO())

    def test_charge_et_met_a_jour(self):
        lancrans = sources.Commune("01205", "COMD", "Lancrans", "01", "01033")
        valserhone = sources.Commune("01033", "COM", "Valserhône", "01")
        saint_pierre = sources.Commune("97502", "COM", "Saint-Pierre", "975")
        self.charger([lancrans, valserhone, saint_pierre])
        self.assertEqual(
            Commune.objects.get(code="01205").commune_parente.nom, "Valserhône"
        )
        self.assertIsNone(Commune.objects.get(code="97502").departement.region)

        valserhone.population = 16423
        self.charger([lancrans, valserhone, saint_pierre])
        self.assertEqual(Commune.objects.get(code="01033").population, 16423)
        self.assertEqual(Commune.objects.count(), 3)
