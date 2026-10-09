"""Les contributions imprimées de l'édition Chabin, retrouvées dans l'OCR des
scans BnF : une référence de découpage sans relecture.

Marie-Anne Chabin a transcrit et séparé chaque contribution ; le titre en dit
la forme (« 3. Mail imprimé, 15 lignes… », « 1. Dactylographié (6 pages)… »).
Pour les contributions dactylographiées et les courriels, on cherche le début
de sa transcription dans la couche texte du scan : la ligne où il commence
est un début de contribution. Les manuscrits ne s'y retrouvent pas, l'OCR du
versement ne les lit pas : ils restent à délimiter à la main (liste
« chabin »).
"""

import re
from collections import Counter
from difflib import SequenceMatcher

# « 3. », ou « C12. » quand l'édition regroupe plusieurs cahiers d'une commune
NUMERO = re.compile(r"^\s*[A-Z]?\d+\s*\.\s*")
DACTYLOGRAPHIE = re.compile(r"dactylograph|tract|(?<!pré)imprim")
IMPRIMEES = {"dactylographié", "mail"}
# ajouts de l'édition : anonymisation ([Nom Prénom]), [sic], notes
CROCHETS = re.compile(r"\[[^\]]*\]")
OUVERTURE = 150  # caractères du début de la transcription cherchés dans l'OCR
LONGUEUR_MOT = 4  # mots plus courts trop communs pour désigner une ligne
CANDIDATS = 200  # lignes au plus comparées pour une contribution
RECUL = 3  # lignes avant une ligne candidate où peut commencer l'ouverture
SEUIL = 0.6  # ressemblance minimale de l'ouverture et de l'OCR


def genre(titre: str) -> str:
    """Forme de la contribution selon son titre : « manuscrit »,
    « dactylographié » ou « mail » (vide si le titre ne la dit pas).

    Elle se lit avant la première virgule : « Manuscrit (coupon préimprimé
    collé) », « Une page dactylographiée pliée collée », « Mail imprimé »."""
    m = NUMERO.match(titre)
    if not m:
        return ""
    forme = titre[m.end() :].split(",")[0].lower()
    if "manuscrit" in forme:
        return "manuscrit"
    if "mail" in forme or "courriel" in forme:
        return "mail"
    if DACTYLOGRAPHIE.search(forme):
        return "dactylographié"
    return ""


def normaliser(texte: str) -> str:
    """Minuscules et mots seuls : la ponctuation varie d'un OCR à l'autre."""
    texte = CROCHETS.sub(" ", texte)
    return " ".join(re.sub(r"\W+", " ", texte.lower()).split())


def localiser(
    transcriptions: list[str], lignes: list[str]
) -> list[tuple[int, float] | None]:
    """Pour chaque transcription, dans l'ordre de l'édition : la ligne de l'OCR
    où elle commence et la ressemblance (0 à 1), ou None si rien n'atteint
    le seuil.

    Les lignes candidates sont celles qui partagent des mots avec l'ouverture
    de la transcription. Des contributions de même ouverture (formulaires) se
    départagent par l'ordre : on prend la première ligne assez ressemblante
    après la contribution précédente, à défaut la plus ressemblante.
    """
    normalisees = [normaliser(x) for x in lignes]
    index: dict[str, list[int]] = {}
    for i, x in enumerate(normalisees):
        for mot in set(x.split()):
            if len(mot) >= LONGUEUR_MOT:
                index.setdefault(mot, []).append(i)

    def fenetre(debut: int, longueur: int) -> str:
        morceaux, n = [], 0
        for x in normalisees[debut:]:
            if x:
                morceaux.append(x)
                n += len(x) + 1
            if n >= longueur:
                break
        return " ".join(morceaux)[:longueur]

    sortie = []
    precedente = -1
    for transcription in transcriptions:
        ouverture = normaliser(transcription)[:OUVERTURE]
        votes = Counter()
        for mot in set(ouverture.split()):
            if len(mot) >= LONGUEUR_MOT:
                votes.update(index.get(mot, []))
        debuts = {
            d
            for j, _ in votes.most_common(CANDIDATS)
            for d in range(max(0, j - RECUL), j + 1)
            if normalisees[d]
        }
        scores = sorted(
            (SequenceMatcher(None, ouverture, fenetre(d, len(ouverture))).ratio(), d)
            for d in debuts
        )
        retenus = [(s, d) for s, d in scores if s >= SEUIL]
        if not ouverture or not retenus:
            sortie.append(None)
            continue
        meilleur = max(s for s, _ in retenus)
        # parmi les quasi-ex æquo du meilleur, le premier après la précédente ;
        # une ligne voisine (numéro de page, tampon) peut précéder la vraie
        # ouverture de peu : on garde la meilleure des lignes toutes proches
        proches = sorted(
            (d, s) for s, d in retenus if s >= meilleur - 0.05 and d > precedente
        )
        if proches:
            groupe = [(s, d) for d, s in proches if d <= proches[0][0] + RECUL]
            s, d = max(groupe, key=lambda x: (x[0], -x[1]))
        else:
            s, d = max(retenus)
        precedente = d
        sortie.append((d, round(s, 3)))
    return sortie
