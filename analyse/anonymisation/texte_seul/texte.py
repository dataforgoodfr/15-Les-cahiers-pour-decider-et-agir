"""Le texte d'une contribution, ses mots non sûrs cachés (#128).

Une ligne est une liste de (mot, caché). Les zones de signature
(`anonymisation.zones`) cachent leurs lignes en entier ; les mots cachés qui
se suivent n'en font qu'un, `CACHE`.
"""

from anonymisation.zones import zones

CACHE = "[…]"


def masquer(lignes: list[list[tuple[str, bool]]]) -> tuple[str, int, int]:
    """Le texte publié de la contribution, son nombre de mots et de mots
    cachés."""
    texte = "\n".join(" ".join(m for m, _ in ligne) for ligne in lignes)
    debuts, position = [], 0
    for ligne in lignes:
        debuts.append(position)
        position += len(" ".join(m for m, _ in ligne)) + 1
    en_zone = {debuts.index(a) for a, _, _ in zones(texte, fin=2, debut=1)}
    sortie, mots, caches = [], 0, 0
    for k, ligne in enumerate(lignes):
        morceaux = []
        for mot, cache in ligne:
            cache = cache or k in en_zone
            mots += 1
            caches += cache
            if not cache:
                morceaux.append(mot)
            elif not morceaux or morceaux[-1] != CACHE:
                morceaux.append(CACHE)
        sortie.append(" ".join(morceaux))
    return "\n".join(sortie), mots, caches
