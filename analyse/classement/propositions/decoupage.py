"""Découper une contribution transcrite en propositions, par règles.

Une contribution de l'édition Chabin mêle des listes (puces, numéros,
souvent sous un intitulé « … : ») et de la prose, dont les lignes sont
coupées par la mise en page du PDF. On recolle ces lignes, puis :

- une ligne marquée (puce, numéro) ouvre une proposition ;
- un intitulé (ligne qui finit par « : », ou ligne courte sans puce suivie
  d'une liste à puces) n'en est pas une : il donne le contexte des
  propositions qui le suivent. Seule, une ligne courte est une proposition
  (« RIC. », « Suppression de la CSG. ») ;
- la prose est coupée en phrases.

Les notes de l'édition entre crochets (anonymisation, [Signature], [sic])
sont retirées, comme les lignes qui ne sont qu'une date. Ce qui n'est pas une proposition (un témoignage, un constat)
est gardé : c'est à la vérification de le marquer.
"""

import re
from dataclasses import dataclass

NOTE = re.compile(r"\[[^\]]*\]")
# Puces de traitement de texte (dont les caractères privés de Symbol, U+F0xx),
# numéros « 1. », « 2) », « 3° », lettres « a) ».
PUCE = re.compile(
    r"^(?:[−–—⎯\-•*●▪■►>➢✓→+·\uf02a\uf0d7\uf0a7\uf0b7]|o(?=\s)"
    r"|\d{1,2}\s*[.)°](?!\d)|[a-z]\))\s*"
)
FIN = re.compile(r"[.!?;:…»)]$")
LARGEUR = 70  # caractères au moins d'une ligne coupée par la mise en page
INTITULE_MOTS = 4  # mots au plus d'un intitulé sans puce
TITRE_MOTS = 8  # mots au plus d'un intitulé sans puce ni ponctuation finale
MOIS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre"
    "|octobre|novembre|décembre|decembre"
)
DATE = re.compile(
    rf"^(?:le\s+|en\s+date\s+du\s+)?\d{{1,2}}(?:er)?[\s/.-]+(?:\d{{1,2}}|{MOIS})"
    r"[\s/.-]+\d{2,4}(?:\s+\d{1,2}[:h]\d{2})?\.?$",
    re.IGNORECASE,
)
# Fin de phrase, avant une majuscule : un point, pas après une initiale
# (« M. MACRON ») ; « ! » ou « ? », même après une espace (« l'ISF ! »).
PHRASE = re.compile(r"(?:(?<=[^\sA-Z][.!?…])|(?<=\s[!?]))\s+(?=[«\"A-ZÀÂÉÈÊÎÔÛÇ])")


@dataclass(frozen=True)
class Proposition:
    texte: str
    contexte: str  # le dernier intitulé, s'il y en a un
    forme: str  # « puce » ou « phrase »


@dataclass
class _Bloc:
    lignes: list[str]
    puce: str  # la puce (« n » pour un numéro, « a » pour une lettre), ou vide

    @property
    def texte(self) -> str:
        return " ".join(self.lignes)


def _blocs(texte: str) -> list[_Bloc]:
    """Les lignes recollées : une ligne coupée par la mise en page suit la
    précédente si elle commence par une minuscule, ou si la précédente est
    longue et sans ponctuation finale."""
    blocs: list[_Bloc] = []
    for brute in texte.split("\n"):
        ligne = " ".join(NOTE.sub(" ", brute).split())
        if not ligne or DATE.match(ligne):
            continue
        m = PUCE.match(ligne)
        if m and ligne[m.end() :]:
            puce = m.group().strip()
            if puce[0].isdigit():
                puce = "n"
            elif puce.endswith(")"):
                puce = "a"
            blocs.append(_Bloc([ligne[m.end() :]], puce))
            continue
        precedente = blocs[-1].lignes[-1] if blocs else ""
        if precedente and (
            ligne[0].islower()
            or (len(precedente) >= LARGEUR and not FIN.search(precedente))
        ):
            blocs[-1].lignes.append(ligne)
        else:
            blocs.append(_Bloc([ligne], ""))
    return blocs


def _intitule(bloc: _Bloc, suivant: _Bloc | None) -> bool:
    texte = bloc.texte
    if texte.endswith(":"):
        return True
    if bloc.puce or not (suivant and suivant.puce):
        return False
    mots = len(texte.split())
    return mots <= INTITULE_MOTS or (not FIN.search(texte) and mots <= TITRE_MOTS)


def decouper(texte: str) -> list[Proposition]:
    """Les propositions, dans l'ordre. Un intitulé à puce ne vaut que pour
    les puces d'un autre genre qui le suivent (ses sous-puces) : la puce
    suivante du même genre le clôt."""
    propositions = []
    intitules: list[tuple[str, str]] = []  # (puce, texte), du plus général
    blocs = _blocs(texte)
    for bloc, suivant in zip(blocs, blocs[1:] + [None]):
        if bloc.puce:
            puces = [p for p, _ in intitules]
            if bloc.puce in puces:
                del intitules[puces.index(bloc.puce) :]
        contexte = intitules[-1][1] if intitules else ""
        if _intitule(bloc, suivant):
            if not bloc.puce:
                intitules.clear()
            intitules.append((bloc.puce, bloc.texte.rstrip(" :.")))
            continue
        if bloc.puce:
            propositions.append(Proposition(bloc.texte, contexte, "puce"))
        else:
            propositions += [
                Proposition(p, contexte, "phrase")
                for p in PHRASE.split(bloc.texte)
                if p
            ]
    return propositions
