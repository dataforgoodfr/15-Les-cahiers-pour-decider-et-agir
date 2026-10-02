import pytest

from communes.representativite import comparer, tranche


@pytest.mark.parametrize(
    ("population", "attendu"),
    [
        (None, "population inconnue"),
        (0, "moins de 200"),
        (199, "moins de 200"),
        (200, "200 à 499"),
        (4_999, "2 000 à 4 999"),
        (100_000, "100 000 et plus"),
    ],
)
def test_tranche(population, attendu):
    assert tranche(population) == attendu


def test_comparer_calcule_couverture_et_representation():
    communes = {
        "A": {"population": 100, "taille": "petite"},
        "B": {"population": 100, "taille": "petite"},
        "C": {"population": 100, "taille": "petite"},
        "D": {"population": 1_000, "taille": "grande"},
    }
    couvertes = {
        "A": {"pages": 10, "texte_natif": 0},
        "D": {"pages": 30, "texte_natif": 15},
    }
    lignes = {lg["taille"]: lg for lg in comparer(communes, couvertes, "taille", True)}

    petite, grande = lignes["petite"], lignes["grande"]
    assert petite["part_communes_couvertes"] == pytest.approx(1 / 3)
    # 3/4 des communes en France, 1/2 dans le corpus
    assert petite["representation"] == pytest.approx((1 / 2) / (3 / 4))
    assert grande["representation"] == pytest.approx((1 / 2) / (1 / 4))
    assert petite["communes_sans_texte_natif"] == 1
    assert grande["part_texte_natif"] == pytest.approx(0.5)
