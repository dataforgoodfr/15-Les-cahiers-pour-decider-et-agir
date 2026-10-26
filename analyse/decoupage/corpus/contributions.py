"""Contributions d'un cahier, de ses débuts trouvés (issue #5).

Les règles et le modèle ne lisent que les pages imprimées (dactylographiées
et mixtes). Une contribution court jusqu'au début suivant, mais s'arrête
avant la première page manuscrite qu'elle rencontrerait : cette page est
peut-être d'un autre auteur, que rien n'a lu. Les pages manuscrites restent
sans contribution.
"""

from dataclasses import dataclass

MANUSCRITE = "manuscrite"


@dataclass
class Debut:
    page: int
    x: float
    y: float
    regle: str


def contributions(debuts: list[Debut], ecrites: list[tuple[int, str]]) -> list[dict]:
    """Une contribution par début, dans l'ordre de lecture des débuts.

    `ecrites` : (numéro, type) des pages écrites du cahier, dans l'ordre.
    La fin est le début suivant, sinon le bas de la dernière page écrite
    avant une page manuscrite, sinon le bas de la dernière page du cahier
    (ces deux fins sans position).
    """
    sortie = []
    for k, d in enumerate(debuts):
        suivant = debuts[k + 1] if k + 1 < len(debuts) else None
        manuscrite = next(
            (n for n, t in ecrites if n > d.page and t == MANUSCRITE), None
        )
        if suivant and (manuscrite is None or suivant.page < manuscrite):
            fin = (suivant.page, suivant.x, suivant.y, "début suivant")
        elif manuscrite is not None:
            avant = max(n for n, _ in ecrites if d.page <= n < manuscrite)
            fin = (avant, None, None, "avant le manuscrit")
        else:
            fin = (ecrites[-1][0], None, None, "fin du cahier")
        sortie.append(
            {
                "rang": k + 1,
                "page_debut": d.page,
                "x_debut": d.x,
                "y_debut": d.y,
                "page_fin": fin[0],
                "x_fin": fin[1],
                "y_fin": fin[2],
                "fin": fin[3],
                "regle": d.regle,
            }
        )
    return sortie
