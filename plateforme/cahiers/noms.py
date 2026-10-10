"""Ce que dit le nom d'un fichier du versement.

`CC_01000_190304_01053_MD_15462.pdf` : catégorie, code postal, date de dépôt
(AAMMJJ), code INSEE, mode, numéro. Les courriers et les comptes rendus n'ont
pas de code INSEE : `CO_01000_190215_D_02389.pdf`.
"""

import re
from datetime import date

from territoires.models import Commune

from .models import Document

NOM = re.compile(
    r"^(?P<categorie>CC|CO|CR|IL)_(?P<code_postal>\d{5})_(?P<date>\d{6})_"
    r"(?:(?P<code_insee>[0-9AB]{5}\w?)_)?(?P<mode>MD|M|D)_(?P<numero>\d+)\.pdf$",
    re.IGNORECASE,
)
# Codes de remplissage, quand la commune n'est pas renseignée à la source.
SANS_COMMUNE = {"00000", "99999"}


def document(fichier: str) -> Document:
    """Le document que désigne ce nom, non enregistré.

    Un nom hors convention donne un document sans autre champ que le fichier ;
    sa catégorie reste à renseigner.
    """
    m = NOM.match(fichier)
    if not m:
        return Document(fichier=fichier)
    aammjj = m["date"]
    try:
        depot = date(2000 + int(aammjj[:2]), int(aammjj[2:4]), int(aammjj[4:]))
    except ValueError:
        depot = None
    code = (m["code_insee"] or "").upper()
    # « 31588s » : le suffixe est ignoré, comme dans `analyse/`.
    commune = None
    if code[:5] and code[:5] not in SANS_COMMUNE:
        commune = Commune.objects.filter(code=code[:5]).first()
    return Document(
        fichier=fichier,
        categorie=m["categorie"].upper(),
        mode=m["mode"].upper(),
        code_postal=m["code_postal"],
        date_depot=depot,
        numero=int(m["numero"]),
        code_insee=code,
        commune=commune,
    )
