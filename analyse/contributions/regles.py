"""Débuts de contributions repérables à la forme du texte (issue #5).

Une contribution est un texte d'un même auteur, ou d'un même groupe, d'un
seul tenant : une liste de propositions numérotées par une même personne en
est une, un compte rendu de réunion aussi. Deux formes la délimitent sans
qu'on ait à comprendre le texte :

- **les courriels imprimés** (environ un quart des cahiers) : un bloc
  d'en-têtes avec un expéditeur et un objet ouvre une contribution. Un
  courriel transféré empile deux blocs presque sans texte entre eux : la
  contribution est le message d'origine, celui du citoyen, pas l'envoi de la
  mairie ;
- **les formulaires** (environ un cahier sur huit) : les mêmes lignes, les
  questions, reviennent d'une page à l'autre. La première d'entre elles, la
  tête du gabarit, ouvre une contribution à chaque fois qu'elle revient.

Les règles ne voient que des lignes et rendent des positions (page, ligne) :
elles ne citent jamais le texte. Un cahier où aucune ne s'applique reste à
découper autrement (méthode à décider).
"""

import re
from collections import Counter
from difflib import SequenceMatcher

EXPEDITEUR = re.compile(r"^\s*(de|from|expéditeur)\s*:", re.IGNORECASE)
OBJET = re.compile(r"^\s*(objet|subject)\s*:", re.IGNORECASE)
COURRIEL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# une adresse, même avec un « @ » abîmé par l'OCR : (a), (9>…
ADRESSE_OCR = re.compile(r"[\w.+-]{2,}(?:@|\(\w{1,2}[)>])[\w-]{2,}")
DESTINATAIRE = re.compile(r"^\s*(?:à|a|to|destinataire)\s*:", re.IGNORECASE)
ENTETE_IMPRIME = 6  # lignes après l'expéditeur où chercher le destinataire
PUBLIC = re.compile(
    r"mairie|ville|gouv|agglo|communaut|m[ée]tropole|d[ée]partement|r[ée]gion|"
    r"pr[ée]fecture|assembl[ée]e|s[ée]nat|elysee|grand-?d[ée]bat",
    re.IGNORECASE,
)
ENTETE = re.compile(
    r"^\s*(de|from|expéditeur|objet|subject|envoyé|sent|date|à|a|to|cc)"
    r"\s*(le)?\s*:",
    re.IGNORECASE,
)
ECART_ENTETES = 3  # lignes au plus entre deux en-têtes d'un même bloc
ECART_TRANSFERT = 3  # lignes non vides au plus entre deux blocs transférés
LONGUEUR_GABARIT = 15  # caractères au moins d'une ligne de gabarit
SIMILARITE = 0.75  # part de caractères communs pour reconnaître une ligne à l'OCR près
ECART_DEBUT = 5  # lignes : un début trouvé si près du début du cahier le remplace
TOLERANCE = 30  # points PDF, environ deux lignes : écart admis avec la référence


def public(texte: str) -> bool:
    """Le texte désigne-t-il une institution (mairie, administration…) ?

    S'il contient une adresse de courriel, seul son domaine compte : « ville »
    dans le nom d'une personne (Villeneuve) ne la rend pas publique."""
    domaines = [a.split("@", 1)[1] for a in COURRIEL.findall(texte)]
    return (
        any(PUBLIC.search(d) for d in domaines)
        if domaines
        else bool(PUBLIC.search(texte))
    )


def entete_imprime(lignes: list[str]) -> int | None:
    """Ligne où commence l'en-tête d'un courriel imprimé depuis une
    messagerie : l'expéditeur (« Prénom Nom <adresse> ») dans les premières
    lignes, puis « À : » ou une seconde adresse, sans « De : » ni « Objet : ».
    """
    pleines = [i for i, x in enumerate(lignes) if x.strip()]
    # l'expéditeur imprimé n'a pas d'étiquette : « De : x@y » est un en-tête classique
    tete = next(
        (
            i
            for i in pleines[:3]
            if ADRESSE_OCR.search(lignes[i]) and not ENTETE.match(lignes[i])
        ),
        None,
    )
    if tete is None:
        return None
    suite = lignes[tete + 1 : tete + 1 + ENTETE_IMPRIME]
    if any(DESTINATAIRE.match(x) or ADRESSE_OCR.search(x) for x in suite):
        return pleines[0]
    return None


def courriels(lignes: list[str]) -> list[int]:
    """Lignes d'une page où commence un courriel.

    Un courriel imprimé depuis une messagerie commence en haut de page par
    son expéditeur ; les messages cités plus bas (« De / Envoyé / Objet »)
    font partie du même échange.

    Un bloc d'en-têtes avec expéditeur et objet ouvre un courriel. Des blocs
    presque sans texte entre eux forment une chaîne (transfert, réponse) :
    la contribution est le message d'origine, le dernier bloc de la chaîne
    dont l'expéditeur n'est pas une institution. Une chaîne envoyée par une
    institution et suivie d'un autre courriel n'est qu'un envoi : elle
    n'ouvre pas de contribution.
    """
    imprime = entete_imprime(lignes)
    if imprime is not None:
        return [imprime]
    blocs: list[list[int]] = []
    for i, ligne in enumerate(lignes):
        if not ENTETE.match(ligne):
            continue
        # un nouvel expéditeur ouvre toujours un nouveau bloc
        meme_bloc = blocs and i - blocs[-1][-1] <= ECART_ENTETES
        if meme_bloc and EXPEDITEUR.match(ligne):
            meme_bloc = not any(EXPEDITEUR.match(lignes[j]) for j in blocs[-1])
        if meme_bloc:
            blocs[-1].append(i)
        else:
            blocs.append([i])
    blocs = [
        b
        for b in blocs
        if any(EXPEDITEUR.match(lignes[i]) for i in b)
        and any(OBJET.match(lignes[i]) for i in b)
    ]
    chaines: list[list[list[int]]] = []
    for bloc in blocs:
        if chaines and (
            sum(bool(x.strip()) for x in lignes[chaines[-1][-1][-1] + 1 : bloc[0]])
            <= ECART_TRANSFERT
        ):
            chaines[-1].append(bloc)
        else:
            chaines.append([bloc])

    def institutionnel(bloc: list[int]) -> bool:
        return any(EXPEDITEUR.match(lignes[i]) and public(lignes[i]) for i in bloc)

    debuts = []
    for k, chaine in enumerate(chaines):
        citoyens = [b for b in chaine if not institutionnel(b)]
        if not citoyens and k + 1 < len(chaines):
            continue  # envoi d'une institution, suivi du vrai courriel
        debuts.append((citoyens or chaine)[-1][0])
    return debuts


def normaliser(ligne: str) -> str:
    return " ".join(ligne.lower().split())


def similarite(ligne: str, modele: str) -> float:
    """Ressemblance d'une ligne normalisée au modèle, à l'OCR près (0 à 1).

    Compare la ligne entière, puis son début : l'OCR fusionne parfois la
    ligne du modèle avec du bruit qui la suit. Le modèle cité au milieu d'une
    phrase ne compte pas."""
    if not ligne:
        return 0.0
    if ligne.startswith(modele):
        return 1.0
    entiere = SequenceMatcher(None, ligne, modele).ratio()
    # le début de ligne ne compte que s'il commence comme le modèle :
    # « du grand débat national organisé… » ne reprend pas l'en-tête
    premier, *_ = ligne.split() or [""]
    if SequenceMatcher(None, premier, modele.split()[0]).ratio() < 0.6:
        return entiere
    debut = ligne[: len(modele) + 3]
    return max(entiere, SequenceMatcher(None, debut, modele).ratio())


def ressemble(ligne: str, modele: str) -> bool:
    return similarite(ligne, modele) >= SIMILARITE


def gabarit(pages: list[list[str]]) -> list[tuple[int, int, str]]:
    """(indice de page, ligne, chemin) où commence chaque formulaire d'un
    cahier ; le chemin dit comment il a été trouvé : « exact »,
    « ressemblant » ou « compagnes ».

    Une ligne est du gabarit si elle revient sur au moins un tiers des pages
    (et au moins trois). Il en faut au moins trois distinctes : un en-tête ou
    un pied de page répété n'est pas un formulaire.

    La tête du gabarit est la ligne du gabarit qui ouvre le plus souvent une
    page. Elle ouvre un formulaire partout où elle revient ; sur une page où
    elle manque, une ligne qui lui ressemble à l'OCR près la remplace, si ce
    n'est pas une autre ligne du gabarit. Quand l'OCR l'a rendue
    méconnaissable, deux lignes de la première page du formulaire (celles qui
    accompagnent la tête) suffisent : le formulaire commence à la première
    d'entre elles.
    """
    if len(pages) < 3:
        return []
    normalisees = [[normaliser(x) for x in lignes] for lignes in pages]
    presences = Counter()
    for lignes in normalisees:
        presences.update({x for x in lignes if len(x) >= LONGUEUR_GABARIT})
    seuil = max(3, len(pages) // 3)
    repetees = {x for x, n in presences.items() if n >= seuil}
    if len(repetees) < 3:
        return []
    premieres = Counter(
        next(x for x in lignes if x in repetees)
        for lignes in normalisees
        if repetees & set(lignes)
    )
    tete = premieres.most_common(1)[0][0]
    avec_tete = [set(lignes) for lignes in normalisees if tete in lignes]
    compagnes = [
        x
        for x in repetees - {tete}
        if sum(x in lignes for lignes in avec_tete) >= len(avec_tete) / 2
    ]
    debuts = []
    for p, lignes in enumerate(normalisees):
        # l'en-tête exact d'abord ; à défaut, une ligne qui lui ressemble sans
        # être elle-même une autre ligne du gabarit (des questions voisines ne
        # diffèrent parfois que d'un mot)
        chemin = "exact"
        trouves = [i for i, x in enumerate(lignes) if x == tete]
        if not trouves:
            chemin = "ressemblant"
            # un seul formulaire par page : la ligne la plus ressemblante, car
            # un en-tête court (« grand débat national ») se cite dans le texte
            scores = [
                (similarite(x, tete), i)
                for i, x in enumerate(lignes)
                if x not in repetees
            ]
            # à score égal, la ligne la plus haute
            meilleur = max(scores, key=lambda x: (x[0], -x[1]), default=(0.0, None))
            trouves = [meilleur[1]] if meilleur[0] >= SIMILARITE else []
        if not trouves:
            chemin = "compagnes"
            appuis = [
                i
                for i, x in enumerate(lignes)
                if x in compagnes or any(ressemble(x, c) for c in compagnes)
            ]
            trouves = appuis[:1] if len(appuis) >= 2 else []
        debuts += [(p, i, chemin) for i in trouves]
    return debuts


def debuts(pages: list[list[str]]) -> list[tuple[int, int, str]]:
    """(indice de page, ligne, règle) des débuts de contributions d'un cahier.

    Le début du cahier ouvre toujours une contribution, sauf si une règle en
    trouve une dans ses toutes premières lignes (un logo ou un titre
    précède souvent l'en-tête du formulaire). Sans autre début trouvé, le
    cahier n'est pas découpé : il n'a que ce début-là.
    """
    trouves = {
        (p, i): "gabarit" if chemin == "exact" else f"gabarit {chemin}"
        for p, i, chemin in gabarit(pages)
    }
    for p, lignes in enumerate(pages):
        for i in courriels(lignes):
            trouves.setdefault((p, i), "courriel")
    premier = next(
        (
            (p, i)
            for p, lignes in enumerate(pages)
            for i, x in enumerate(lignes)
            if x.strip()
        ),
        None,
    )
    if premier and not any(
        p == premier[0] and i - premier[1] <= ECART_DEBUT for p, i in trouves
    ):
        trouves[premier] = "début du cahier"
    return sorted((p, i, regle) for (p, i), regle in trouves.items())


def evaluer(
    predits: list[tuple[str, int, float]],
    reference: list[tuple[str, int, float]],
    tolerance: float = TOLERANCE,
) -> tuple[float, float]:
    """Précision et rappel des débuts (fichier, page, ordonnée en points).

    Un début trouvé est juste s'il tombe, sur la même page, à moins de
    `tolerance` points d'un début de la référence encore libre.
    """
    libres: dict[tuple[str, int], list[float]] = {}
    for fichier, page, y in reference:
        libres.setdefault((fichier, page), []).append(y)
    justes = 0
    for fichier, page, y in sorted(predits):
        candidats = libres.get((fichier, page), [])
        proche = min(candidats, key=lambda r: abs(r - y), default=None)
        if proche is not None and abs(proche - y) <= tolerance:
            candidats.remove(proche)
            justes += 1
    precision = justes / len(predits) if predits else 0.0
    rappel = justes / len(reference) if reference else 0.0
    return precision, rappel
