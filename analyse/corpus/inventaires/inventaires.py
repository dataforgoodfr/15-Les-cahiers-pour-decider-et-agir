"""Documents manquants : inventaires du versement contre fichiers (issue #43).

Les Archives nationales ont publié, pour chaque département, la liste des
contributions numérisées (`A_lire/*_inventaire_contributions.pdf`) : une
ligne par document, avec sa commune, sa catégorie (CC, CO, CR, IL), son
nombre de pages et son nom de fichier. On lit ces tableaux, puis on les
rapproche des fichiers du versement, nom par nom.

Deux pièges des inventaires :

- l'inventaire « sans provenance identifiée » (00) écrit les noms sans
  `.pdf` ;
- un même nom peut figurer dans deux inventaires. Celui des Côtes-d'Armor
  (22) reproduit la liste du Calvados (14) sous sa propre couverture : le
  document revient à l'inventaire du dossier où se trouve son fichier.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

CATEGORIES = ("CC", "CO", "CR", "IL")
_DEPARTEMENT = re.compile(r"_(\d\d)_")
_SOULIGNE = re.compile(r"^[_ ]+$")


@dataclass
class Entree:
    fichier: str
    categorie: str
    departement: str  # celui de l'inventaire
    code_insee: str
    pages: int


@dataclass
class Document:
    fichier: str
    categorie: str
    departement: str
    code_insee: str
    inventaires: int  # inventaires qui le listent
    present: bool
    pages_attendues: int | None
    pages_presentes: int | None


def departement(chemin: Path) -> str:
    """Le département d'un inventaire ou d'un dossier `BnF_GDN_XX_PDF`."""
    return _DEPARTEMENT.search(chemin.name).group(1)


def nom_de_fichier(cellule: str) -> str:
    """Le nom de fichier d'une cellule : soulignés lus comme des espaces, ligne
    de soulignés en trop, extension parfois absente."""
    lignes = [lg for lg in cellule.splitlines() if not _SOULIGNE.match(lg)]
    nom = "_".join(" ".join(lignes).split())
    return nom if nom.endswith(".pdf") else nom + ".pdf"


def entree(ligne: list, dep: str) -> Entree | None:
    """Une ligne du tableau, ou None pour l'en-tête et les titres de section."""
    if len(ligne) != 6 or ligne[3] not in CATEGORIES:
        return None
    _, _, insee, categorie, pages, fichier = ligne
    return Entree(nom_de_fichier(fichier), categorie, dep, insee or "", int(pages))


def lire_inventaire(chemin: Path) -> list[Entree]:
    dep = departement(chemin)
    entrees = []
    with pymupdf.open(chemin) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                entrees += filter(None, (entree(lg, dep) for lg in table.extract()))
    return entrees


def pages(chemin: Path) -> tuple[str, str, int]:
    """Nom, département (dossier) et nombre de pages d'un fichier du versement."""
    with pymupdf.open(chemin) as doc:
        return chemin.name, departement(chemin.parent.parent), doc.page_count


def rapprocher(
    entrees: list[Entree], presents: dict[str, tuple[str, int]]
) -> list[Document]:
    """Un document par nom de fichier, inventorié ou présent. `presents` donne,
    pour chaque fichier du versement, son département (dossier) et ses pages."""
    par_nom = {}
    for e in entrees:
        par_nom.setdefault(e.fichier, []).append(e)
    documents = []
    for nom in sorted(par_nom.keys() | presents.keys()):
        listees = par_nom.get(nom, [])
        dossier, pages = presents.get(nom, (None, None))
        e = next((e for e in listees if e.departement == dossier), None)
        e = e or (listees[0] if listees else None)
        documents.append(
            Document(
                nom,
                nom[:2],
                dossier or e.departement,
                e.code_insee if e else "",
                len(listees),
                nom in presents,
                e.pages if e else None,
                pages,
            )
        )
    return documents
