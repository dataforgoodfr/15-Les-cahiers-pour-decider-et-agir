"""Pages manquantes des courriers et formulaires types (issue #43).

Des courriers de campagne et des formulaires reviennent dans des centaines de
cahiers. Quand on connaît un modèle en entier, un exemplaire auquel il manque
une page trahit une page perdue à la numérisation ou au versement.

On lit la couche texte, sans OCR, en trois temps :

1. les **lignes fréquentes** : une ligne présente dans au moins 30 fichiers
   appartient à un modèle ;
2. les **modèles** : les lignes qui reviennent dans les mêmes fichiers sont
   regroupées, puis découpées en pages d'après leurs exemplaires complets.
   Les pages de service (attestation de remise, page de garde, page de
   clôture) sont écartées : elles encadrent le cahier, et leur absence ne dit
   rien d'une page de courrier perdue. De même pour les en-têtes, lignes
   imprimées sur chaque feuille d'un cahier. Chaque page du modèle est
   décrite par ses paires de mots consécutifs ; une page de modèle de moins
   de 10 paires se retrouverait par hasard, elle est écartée ;
3. les **exemplaires** : une page porte une page du modèle si elle en contient
   au moins la moitié des paires de mots ; un courrier court peut tenir sur
   une seule page, qui en porte alors plusieurs. Les paires résistent au
   découpage des lignes par l'OCR et à quelques mots mal lus ; une page sans
   rapport n'en a presque aucune.

Un même courrier existe souvent en plusieurs modèles presque identiques : une
page peut alors porter des exemplaires de plusieurs modèles. Dans chaque
fichier, on garde le meilleur (le plus de pages du modèle, puis les pages les
mieux reconnues), et on écarte ceux qui partagent une de ses pages.

Un exemplaire incomplet n'a pas toujours perdu une page. Un même courrier
circule parfois en plusieurs **versions**, une courte et une longue : un
exemplaire partiel fréquent, qui finit toujours par les mêmes mots, et pas par
la fin de la version complète, est une version. Les autres sont incomplets ;
la **ponctuation** dit si la page voisine du trou commence ou finit au milieu
d'une phrase, ce qui confirme la coupure. Une page voisine sans couche texte
(manuscrite, tournée) a pu porter la page qui manque : elle est signalée.
"""

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations, pairwise

MOTS_PAR_LIGNE = (2, 14)
CARACTERES_MIN = 8
FICHIERS_MIN = 30  # fichiers où une ligne revient pour appartenir à un modèle
JACCARD_MIN = 0.5  # deux lignes du même modèle partagent leurs fichiers
LIGNES_MIN = 6  # lignes d'un modèle
LIGNES_PAR_FICHIER_MAX = 200  # au-delà, un recueil de modèles : ignoré
COMPLET = 0.9  # part des lignes d'un exemplaire complet
ETENDUE_MAX = 12  # pages d'un exemplaire, au plus
LIGNES_PAR_PAGE_MIN = 2  # lignes d'une page de modèle
PAIRES_PAR_PAGE_MIN = 10  # paires de mots d'une page de modèle
SEUIL_PAGE = 0.5  # part des paires de mots d'une page de modèle
ECART_MAX = 2  # pages entre deux pages d'un même exemplaire (verso vierge)
VERSION_MIN = 5  # exemplaires partiels identiques qui font une version
MOTS_FIN = 3  # mots de fin qui identifient une version
MOTS_PHRASE = 3  # mots d'une ligne de texte suivi (hors titres, numéros)
MOTS_LISIBLE = 20  # mots d'une page dont la couche texte est lisible
_FIN_DE_PHRASE = re.compile(r"[.!?…:;»\"')\]]\s*$")
_PAGE_DE_SERVICE = re.compile(
    r"\b(attestation de remise|certifie avoir recu|porte le n|cachet de la mairie"
    r"|pages vierges)\b"
)
SERVICE = {
    "cahier citoyen",
    "fin des pages ecrites",
    "grand debat national",
    "le grand debat national",
    "code postal",
    "ville code insee",
}

COMPLET_ = "complet"
VERSION = "version"
INCOMPLET = "incomplet"


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = re.sub(r"[._…]{2,}", " ", texte.lower())
    return " ".join(re.sub(r"[^a-z0-9]", " ", texte).split())


def lignes(texte: str) -> set[str]:
    """Les lignes normalisées d'une page qui peuvent appartenir à un modèle."""
    gardees = set()
    for ligne in texte.splitlines():
        n = normaliser(ligne)
        mots = len(n.split())
        if (
            MOTS_PAR_LIGNE[0] <= mots <= MOTS_PAR_LIGNE[1]
            and len(n) >= CARACTERES_MIN
            and n not in SERVICE
        ):
            gardees.add(n)
    return gardees


def paires(texte: str) -> set[tuple[str, str]]:
    """Les paires de mots consécutifs du texte normalisé."""
    mots = normaliser(texte).split()
    return set(pairwise(mots))


def regrouper(lignes_par_fichier: dict[str, set[str]]) -> list[list[str]]:
    """Groupes de lignes fréquentes qui reviennent dans les mêmes fichiers."""
    fichiers = defaultdict(set)
    for nom, ls in lignes_par_fichier.items():
        for ligne in ls:
            fichiers[ligne].add(nom)
    frequentes = {lg: f for lg, f in fichiers.items() if len(f) >= FICHIERS_MIN}
    parent = {lg: lg for lg in frequentes}

    def racine(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    communes = Counter()
    for ls in lignes_par_fichier.values():
        ls = sorted(ls & frequentes.keys())
        if len(ls) <= LIGNES_PAR_FICHIER_MAX:
            communes.update(combinations(ls, 2))
    for (a, b), k in communes.items():
        if k / (len(frequentes[a]) + len(frequentes[b]) - k) >= JACCARD_MIN:
            parent[racine(a)] = racine(b)
    groupes = defaultdict(list)
    for ligne in sorted(frequentes):
        groupes[racine(ligne)].append(ligne)
    return [g for g in groupes.values() if len(g) >= LIGNES_MIN]


def structurer(groupe: list[str], fichiers: dict[str, list[set[str]]]) -> list[set]:
    """Les pages du modèle, d'après ses exemplaires complets : la page
    relative la plus fréquente de chaque ligne, hors en-têtes (lignes sur
    plusieurs pages d'un même exemplaire). Une liste de jeux de lignes."""
    lignes_du_groupe = set(groupe)
    pages_relatives = defaultdict(list)
    repetitions = defaultdict(list)
    for pages in fichiers.values():
        portees = [(p, ls & lignes_du_groupe) for p, ls in enumerate(pages)]
        portees = [(p, ls) for p, ls in portees if ls]
        if not portees or portees[-1][0] - portees[0][0] >= ETENDUE_MAX:
            continue
        if len(set().union(*(ls for _, ls in portees))) < COMPLET * len(groupe):
            continue
        for p, ls in portees:
            for ligne in ls:
                pages_relatives[ligne].append(p - portees[0][0])
        for ligne, n in Counter(lg for _, ls in portees for lg in ls).items():
            repetitions[ligne].append(n)
    pages = defaultdict(set)
    for ligne, relatives in pages_relatives.items():
        if statistics.median(repetitions[ligne]) == 1:
            pages[statistics.mode(relatives)].add(ligne)
    return [
        ls
        for _, ls in sorted(pages.items())
        if len(ls) >= LIGNES_PAR_PAGE_MIN
        and len(set().union(*map(paires, ls))) >= PAIRES_PAR_PAGE_MIN
        and not any(_PAGE_DE_SERVICE.search(lg) for lg in ls)
    ]


@dataclass
class Modele:
    numero: int
    pages: list[set[tuple[str, str]]]  # paires de mots de chaque page


def modele(numero: int, pages_de_lignes: list[set[str]]) -> Modele:
    return Modele(
        numero, [set().union(*(paires(lg) for lg in ls)) for ls in pages_de_lignes]
    )


def exemplaires(pages: list[set[tuple[str, str]]], m: Modele) -> list[list[tuple]]:
    """Les exemplaires du modèle dans un fichier : suites de (page du fichier,
    page du modèle), triées dans l'ordre du modèle. Les pages d'un exemplaire
    se suivent de près, dans n'importe quel ordre (feuille numérisée à
    l'envers), sans qu'une page du modèle revienne."""
    trouves = []
    for p, pp in enumerate(pages):
        for k, empreinte in enumerate(m.pages):
            if len(empreinte & pp) >= SEUIL_PAGE * len(empreinte):
                suite = trouves[-1] if trouves else []
                if (
                    suite
                    and k not in {kk for _, kk in suite}
                    and p - suite[-1][0] <= ECART_MAX
                ):
                    suite.append((p, k))
                else:
                    trouves.append([(p, k)])
    return [sorted(suite, key=lambda pk: pk[1]) for suite in trouves]


def _lignes_de_texte(texte: str) -> list[str]:
    return [lg.strip() for lg in texte.splitlines() if len(lg.split()) >= MOTS_PHRASE]


def commence_en_cours(texte: str) -> bool:
    """La page commence au milieu d'une phrase : première ligne en minuscule."""
    ls = _lignes_de_texte(texte)
    lettres = [c for c in ls[0] if c.isalpha()] if ls else []
    return bool(lettres) and lettres[0].islower()


def finit_en_cours(texte: str) -> bool:
    """La page finit au milieu d'une phrase : dernière ligne sans ponctuation finale."""
    ls = _lignes_de_texte(texte)
    return bool(ls) and not _FIN_DE_PHRASE.search(ls[-1])


@dataclass
class Exemplaire:
    fichier: str
    modele: int
    pages: list[int]  # pages du fichier, à partir de 1
    portees: list[int]  # pages du modèle trouvées
    fin: str  # derniers mots de la dernière page trouvée
    debut_coupe: bool
    fin_coupee: bool
    avant_illisible: bool  # la page qui précède n'a pas de texte lisible
    apres_illisible: bool
    part: float = 1.0  # part moyenne des paires de mots des pages trouvées


def decrire(fichier: str, textes: list[str], m: Modele) -> list[Exemplaire]:
    """Les exemplaires du modèle dans un fichier, avec ce qu'il faut pour les classer."""
    pages = [paires(t) for t in textes]

    def illisible(p):
        return 0 <= p < len(textes) and len(textes[p].split()) < MOTS_LISIBLE

    resultat = []
    for suite in exemplaires(pages, m):
        premiere, derniere = suite[0][0], suite[-1][0]
        resultat.append(
            Exemplaire(
                fichier,
                m.numero,
                [p + 1 for p, _ in suite],
                [k for _, k in suite],
                " ".join(normaliser(textes[derniere]).split()[-MOTS_FIN:]),
                commence_en_cours(textes[premiere]),
                finit_en_cours(textes[derniere]),
                illisible(premiere - 1),
                illisible(derniere + 1),
                statistics.mean(
                    len(m.pages[k] & pages[p]) / len(m.pages[k]) for p, k in suite
                ),
            )
        )
    return resultat


def departager(
    tous: list[Exemplaire], pages_par_modele: dict[int, int]
) -> list[Exemplaire]:
    """Les exemplaires d'un fichier, sans ceux qui partagent une page avec un
    meilleur : plus de pages du modèle trouvées, puis mieux reconnues."""
    gardes, prises = [], set()
    for e in sorted(
        tous,
        key=lambda e: (len(e.portees) / pages_par_modele[e.modele], e.part),
        reverse=True,
    ):
        if prises.isdisjoint(e.pages):
            gardes.append(e)
            prises.update(e.pages)
    return gardes


def classer(tous: list[Exemplaire], pages_par_modele: dict[int, int]):
    """Statut de chaque exemplaire (complet, version, incomplet) et pages du
    modèle qui lui manquent."""
    fins_completes = defaultdict(set)
    partiels = Counter()
    for e in tous:
        if len(e.portees) == pages_par_modele[e.modele]:
            fins_completes[e.modele].add(e.fin)
        else:
            partiels[(e.modele, tuple(e.portees), e.fin)] += 1
    for e in tous:
        n = pages_par_modele[e.modele]
        manquantes = [k for k in range(n) if k not in e.portees]
        if not manquantes:
            yield e, COMPLET_, []
        elif (
            partiels[(e.modele, tuple(e.portees), e.fin)] >= VERSION_MIN
            and e.fin not in fins_completes[e.modele]
        ):
            yield e, VERSION, []
        else:
            yield e, INCOMPLET, manquantes


def coupure(e: Exemplaire, manquantes: list[int]) -> bool:
    """La ponctuation confirme le trou : page coupée du côté de la page manquante."""
    avant = any(k < e.portees[0] for k in manquantes)
    apres = any(k > e.portees[-1] for k in manquantes)
    milieu = any(e.portees[0] < k < e.portees[-1] for k in manquantes)
    return milieu or (avant and e.debut_coupe) or (apres and e.fin_coupee)


def illisible(e: Exemplaire, manquantes: list[int]) -> bool:
    """La page voisine du trou n'a pas de texte lisible : elle a pu le porter."""
    avant = any(k < e.portees[0] for k in manquantes)
    apres = any(k > e.portees[-1] for k in manquantes)
    return (avant and e.avant_illisible) or (apres and e.apres_illisible)
