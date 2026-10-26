"""Texte d'une contribution, mots non sûrs cachés."""

from anonymisation.texte_seul.texte import CACHE, masquer

CORPS = (
    "Nous demandons que les services publics restent ouverts dans les villages "
    "et que la poste ne ferme pas"
)


def ligne(texte, caches=()):
    return [(m, m in caches) for m in texte.split()]


def test_les_mots_caches_qui_se_suivent_n_en_font_qu_un():
    lignes = [ligne(CORPS), ligne(CORPS, {"services", "publics"}), ligne(CORPS)]
    texte, mots, caches = masquer(lignes)
    assert texte.splitlines()[1].split().count(CACHE) == 1
    assert (mots, caches) == (54, 2)


def test_la_signature_est_cachee_en_entier():
    lignes = [ligne(CORPS), ligne(CORPS), ligne("Jean Dupont")]
    texte, _, caches = masquer(lignes)
    assert texte.splitlines()[-1] == CACHE
    assert caches == 2
