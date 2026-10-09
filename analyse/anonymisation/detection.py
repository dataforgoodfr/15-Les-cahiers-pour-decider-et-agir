"""Données personnelles repérables sans comprendre le texte (issue #7).

Deux sources de repérages, que l'annotation fait vérifier à la main :

- **la forme des mots**, dans la couche texte (OCR du versement) :
  - les adresses de courriel, même quand l'OCR abîme le « @ » (« (a) »,
    « (9) ») ou perd le point du domaine. Une adresse n'est publique que si
    son domaine est celui d'une institution (mot clé, ou nom de la commune
    du cahier) et sa partie locale générique (contact@, mairie@…) :
    prenom.nom@ville-x.fr désigne un agent, c'est une donnée personnelle ;
  - les numéros de téléphone ;
  - les noms : une civilité suivie d'un nom, un prénom (fichier des
    prénoms de l'INSEE) suivi d'un mot à majuscule, un nom en capitales
    suivi d'un prénom ;
  - les adresses postales : un numéro suivi d'un type de voie, un code
    postal suivi d'une ville ;
- **les zones de formulaire** : un formulaire type place les coordonnées
  toujours au même endroit. Les rectangles de données personnelles posés à
  la main sur quelques exemplaires, rapportés à l'en-tête du formulaire, se
  reportent sur tous les exemplaires du cahier. L'en-tête vient des règles
  de `contributions`, qui ne lisent que les pages dactylographiées ; un
  formulaire rempli à la main se reconnaît plutôt à ses lignes imprimées,
  apprises sur les pages annotées (`modele_appris`).

Mieux vaut masquer une donnée de trop que laisser passer celle d'un
citoyen : dans le doute, une adresse est personnelle. Une adresse n'est
écartée que si elle est sûrement publique ; seuls les noms répandus d'un
cahier à l'autre (personnalités) sont écartés pour leur fréquence. Les repérages sont des
cadres en points PDF, jamais le texte repéré.
"""

import csv
import io
import re
import unicodedata
import zipfile
from collections import Counter
from difflib import SequenceMatcher
from statistics import median

from contributions.regles import PUBLIC

EXTENSIONS = r"(?:fr|com|net|org|eu|be|ch|info|biz|io|de|uk|it|es|lu|re)"
COURRIEL = re.compile(
    r"(?P<local>[\w.+-]{2,})"
    # le « @ », ou une lecture de l'OCR : un ou deux signes entre parenthèses,
    # (a), (9), (g>, ©… ; le domaine doit alors finir par une extension connue
    r"(?:@|(?P<ocr>\(\w{1,2}[)>]|©))"
    r"(?P<domaine>[\w-]{2,}(?:\.[\w-]{2,})*)"
)
GENERIQUES = re.compile(
    r"^(?:contact|info|infos|accueil|mairie|secretariat|courrier|communication|"
    r"cabinet|maire|dgs|debat|granddebat|grand-debat|webmaster|noreply|no-reply|"
    r"ne-pas-repondre|service|services|population|etat-civil|urbanisme|ccas)",
    re.IGNORECASE,
)
# 10 chiffres groupés par deux (0X XX XX XX XX), ou +33 X XX XX XX XX
TELEPHONE = re.compile(r"(?:\+33\s?[1-9]|\b0[1-9])(?:[\s.-]?\d{2}){4}\b")
CIVILITE = re.compile(
    r"\b(?:M\.|Mr\.?|Mme\.?|Mlle\.?|Monsieur|Madame|Mademoiselle|Dr\.?|Me\.?)\s+"
    r"(?:[A-ZÀ-Ý][\w'-]+\s*){1,3}"
)
VOIE = re.compile(
    r"\b\d{1,4}\s?(?:bis|ter)?,?\s+(?:rue|avenue|av\.?|boulevard|bd|chemin|all[ée]e|"
    r"impasse|place|route|quai|cours|square|r[ée]sidence|lotissement|lieu-dit|"
    r"hameau|passage|cit[ée]|mont[ée]e|sentier|voie)\b[^,;\n]{0,40}",
    re.IGNORECASE,
)
CODE_POSTAL = re.compile(r"\b\d{5}\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ' -]{2,30}")
TITRE = re.compile(
    r"\S+\s+(?:le|la|les|l')\s*(?:maire|pr[ée]sident|ministre|pr[ée]fet|d[ée]put[ée]|"
    r"s[ée]nat|conseill|adjoint|directeur|directrice|commissaire)",
    re.IGNORECASE,
)
LIEUX = {
    "rue",
    "avenue",
    "boulevard",
    "bd",
    "place",
    "allée",
    "allee",
    "impasse",
    "chemin",
    "quai",
    "cours",
    "square",
    "lycée",
    "lycee",
    "collège",
    "college",
    "école",
    "ecole",
    "hôpital",
    "hopital",
    "centre",
    "salle",
    "stade",
    "parc",
    "pont",
    "gare",
    "résidence",
    "residence",
    "cité",
    "cite",
    "fondation",
}
REPANDUE = 3  # cahiers au moins où revient le nom d'une personnalité
MOTS_CAPITALES = {"LE", "LA", "LES", "DE", "DES", "DU", "ET", "EN", "AU", "AUX", "UN"}
NAISSANCES = 200  # naissances au moins (depuis 1900) pour qu'un prénom compte
MARGE = 4  # points ajoutés autour d'une zone reportée
CHEVAUCHEMENT = 0.3  # recouvrement minimal de deux rectangles d'une même zone
EXEMPLAIRES = 2  # exemplaires annotés au moins pour reporter une zone
LIGNES_MODELE = 2  # lignes imprimées du modèle au moins sur un exemplaire


def charger_prenoms(contenu: bytes) -> set[str]:
    """Prénoms du fichier national de l'INSEE (zip), en minuscules."""
    totaux: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        nom = archive.namelist()[0]
        texte = io.TextIOWrapper(archive.open(nom), encoding="utf-8")
        for ligne in csv.DictReader(texte, delimiter=";"):
            prenom = ligne["preusuel"]
            if not prenom.startswith("_"):
                totaux[prenom.lower()] = totaux.get(prenom.lower(), 0) + int(
                    ligne["nombre"]
                )
    return {p for p, n in totaux.items() if n >= NAISSANCES and len(p) > 1}


def _simple(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFD", texte.lower())
    return re.sub(r"[^a-z0-9]", "", sans_accents.encode("ascii", "ignore").decode())


def domaine_public(domaine: str, commune: str = "") -> bool:
    """Domaine d'une institution : mot clé, ou nom de la commune du cahier
    (lavoulte.fr pour La Voulte-sur-Rhône), à l'OCR près."""
    if PUBLIC.search(domaine):
        return True
    nom = _simple(commune)[:8]
    etiquette = _simple(domaine.split(".")[0])
    if len(nom) < 4:
        return False
    return nom in etiquette or (
        SequenceMatcher(None, etiquette[: len(nom)], nom).ratio() >= 0.8
    )


def adresse_personnelle(local: str, domaine: str, commune: str = "") -> bool:
    """Une adresse de courriel désigne-t-elle une personne ?"""
    if not domaine_public(domaine, commune):
        return True
    morceaux = [m for m in re.split(r"[._-]", local) if m]
    # prenom.nom@institution : un agent, donc une personne
    return len(morceaux) >= 2 and not GENERIQUES.match(local)


def mots_personnels(
    mots: list[tuple], commune: str = "", prenoms: frozenset = frozenset()
) -> list[dict]:
    """Courriels, téléphones, noms et adresses postales d'une page.

    `mots` : la sortie de `page.get_text("words")`, (x0, y0, x1, y1, texte,
    bloc, ligne, rang). On cherche dans le texte de chaque ligne ; le cadre
    d'un repérage réunit les mots qu'il couvre.
    """
    reperes = []
    lignes: dict[tuple, list] = {}
    for m in mots:
        lignes.setdefault((m[5], m[6]), []).append(m)
    for ligne in lignes.values():
        ligne.sort(key=lambda m: m[7])
        texte, debuts = "", []
        for m in ligne:
            debuts.append(len(texte))
            texte += m[4] + " "

        def cadre(debut, fin, etiquette, ligne=ligne, debuts=debuts, texte=texte):
            # « cle » sert à compter les cahiers où revient la même donnée ;
            # elle ne sort jamais du module (voir `retirer_cles`)
            return _couvrir(ligne, debuts, debut, fin, etiquette) | {
                "cle": _simple(texte[debut:fin])
            }

        for t in COURRIEL.finditer(texte):
            domaine = t.group("domaine")
            if t.group("ocr") and not re.search(rf"\.{EXTENSIONS}$", domaine):
                continue
            sans_point = "." not in domaine
            # un domaine sans point n'est une adresse qu'entre chevrons ou après mailto
            if sans_point and not re.search(r"[<:\[]\S*$", texte[: t.start() + 1]):
                continue
            if adresse_personnelle(t.group("local"), domaine, commune):
                reperes.append(cadre(t.start(), t.end(), "courriel"))
        for motif, etiquette in (
            (TELEPHONE, "téléphone"),
            (VOIE, "adresse"),
            (CODE_POSTAL, "adresse"),
            (CIVILITE, "nom"),
        ):
            for t in motif.finditer(texte):
                if motif is CIVILITE and TITRE.match(texte, t.start()):
                    continue  # « Monsieur le Maire », « Madame la Ministre »
                reperes.append(cadre(t.start(), t.end(), etiquette))
        reperes += [cadre(d, f, "nom") for d, f in _noms(ligne, debuts, prenoms)]
    return reperes


def _couvrir(ligne: list, debuts: list[int], debut: int, fin: int, etiquette: str):
    """Cadre réunissant les mots de la ligne couverts par [debut, fin[."""
    couverts = [m for m, d in zip(ligne, debuts) if d < fin and d + len(m[4]) > debut]
    return _cadre(
        min(m[0] for m in couverts),
        min(m[1] for m in couverts),
        max(m[2] for m in couverts),
        max(m[3] for m in couverts),
        etiquette,
    )


def _noms(ligne: list, debuts: list[int], prenoms: frozenset) -> list[tuple]:
    """Prénom + mot à majuscule, ou NOM en capitales + prénom (positions)."""
    trouves = []
    for k in range(len(ligne) - 1):
        a, b = ligne[k][4].strip(",;:."), ligne[k + 1][4].strip(",;:.")
        if not (a[:1].isupper() and b[:1].isupper()):
            continue
        avant = ligne[k - 1][4].lower().strip(",;:.") if k else ""
        if avant in LIEUX:
            continue  # rue Jean Jaurès, lycée Victor Hugo
        prenom_nom = a.lower() in prenoms and len(b) > 1 and not b.lower() in prenoms
        nom_prenom = (
            a.isupper()
            and len(a) > 1
            and a not in MOTS_CAPITALES
            and b.lower() in prenoms
        )
        if prenom_nom or nom_prenom:
            trouves.append((debuts[k], debuts[k + 1] + len(ligne[k + 1][4])))
    return trouves


def _cadre(x0, y0, x1, y1, etiquette: str) -> dict:
    return {
        "x0": round(x0, 1),
        "y0": round(y0, 1),
        "x1": round(x1, 1),
        "y1": round(y1, 1),
        "etiquette": etiquette,
    }


def retirer_repandues(par_cahier: dict[str, list[dict]]) -> list[dict]:
    """Écarte les noms qui reviennent dans REPANDUE cahiers ou plus : le nom
    d'un particulier ne court pas d'un cahier à l'autre, celui d'une
    personnalité si. Les adresses et les téléphones restent tous : dans le
    doute, on cache (un militant écrit à plusieurs mairies). Retire la clé
    interne de chaque repérage."""
    cahiers: dict[str, set] = {}
    for fichier, reperes in par_cahier.items():
        for r in reperes:
            cahiers.setdefault(r["cle"], set()).add(fichier)
    garde = []
    for fichier, reperes in par_cahier.items():
        for r in reperes:
            if r["etiquette"] != "nom" or len(cahiers[r["cle"]]) < REPANDUE:
                garde.append(
                    {"fichier": fichier} | {k: v for k, v in r.items() if k != "cle"}
                )
    return garde


def recouvrement(a: dict, b: dict) -> float:
    """Aire commune rapportée à la plus petite des deux aires. Un point (aire
    nulle) recouvre entièrement un rectangle qui le contient."""
    for point, autre in ((a, b), (b, a)):
        if point["x1"] - point["x0"] <= 0 or point["y1"] - point["y0"] <= 0:
            x = (point["x0"] + point["x1"]) / 2
            y = (point["y0"] + point["y1"]) / 2
            dedans = autre["x0"] <= x <= autre["x1"] and autre["y0"] <= y <= autre["y1"]
            return 1.0 if dedans else 0.0
    largeur = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    hauteur = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if largeur <= 0 or hauteur <= 0:
        return 0.0
    aire = min(
        (a["x1"] - a["x0"]) * (a["y1"] - a["y0"]),
        (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]),
    )
    return largeur * hauteur / aire if aire > 0 else 0.0


def zones(annotees: list[dict]) -> list[dict]:
    """Zones de formulaire, d'après les rectangles annotés sur ses exemplaires.

    `annotees` : rectangles de données personnelles déjà rapportés à l'en-tête
    de leur exemplaire (origine au coin haut gauche de l'en-tête), avec leur
    étiquette et leur page. Les rectangles de même étiquette qui se
    recouvrent forment une zone ; elle n'est gardée que si elle vient d'au
    moins EXEMPLAIRES exemplaires. La zone réunit ses rectangles, plus une
    marge.
    """
    groupes: list[list[dict]] = []
    for r in annotees:
        for g in groupes:
            if g[0]["etiquette"] == r["etiquette"] and any(
                recouvrement(r, autre) >= CHEVAUCHEMENT for autre in g
            ):
                g.append(r)
                break
        else:
            groupes.append([r])
    sortie = []
    for g in groupes:
        if len({r["page"] for r in g}) < EXEMPLAIRES:
            continue
        sortie.append(
            {
                "x0": min(r["x0"] for r in g) - MARGE,
                "y0": min(r["y0"] for r in g) - MARGE,
                "x1": max(r["x1"] for r in g) + MARGE,
                "y1": max(r["y1"] for r in g) + MARGE,
                "etiquette": g[0]["etiquette"],
                "exemplaires": len({r["page"] for r in g}),
            }
        )
    return sortie


Lignes = dict[str, tuple[float, float]]  # ligne normalisée -> coin haut gauche


def modele_appris(pages: dict[int, Lignes], annotees: list[dict]) -> list[dict]:
    """Zones de données personnelles d'un cahier, reportées sur chaque
    exemplaire de leur formulaire, appris sur les pages annotées.

    `pages` : lignes de chaque page du cahier, normalisées, avec leur
    position ; `annotees` : rectangles de données personnelles posés à la
    main (page, cadre, étiquette). Les rectangles de même étiquette posés au
    même endroit d'au moins EXEMPLAIRES pages forment un groupe ; un cahier
    peut mêler plusieurs formulaires, et des lettres, chaque groupe apprend
    donc son propre modèle (`_reporter`)."""
    reperes = []
    for brute in zones(annotees):
        groupe = [
            r
            for r in annotees
            if r["etiquette"] == brute["etiquette"]
            and recouvrement(r, brute) >= CHEVAUCHEMENT
        ]
        reperes += _reporter(pages, groupe)
    return reperes


def _reporter(pages: dict[int, Lignes], groupe: list[dict]) -> list[dict]:
    """Le modèle d'un groupe est fait des lignes qui reviennent sur au moins
    EXEMPLAIRES de ses pages ; une page qui en porte au moins LIGNES_MODELE
    est un exemplaire, qu'elle soit typée dactylographiée ou manuscrite. Son
    décalage (numérisation) est le décalage médian de ces lignes. Les
    rectangles du groupe, ramenés au même repère, forment la zone reportée."""
    exemplaires = {r["page"] for r in groupe}
    presences = Counter(x for p in exemplaires for x in pages.get(p, {}))
    modele = {x for x, n in presences.items() if n >= EXEMPLAIRES}
    if len(modele) < LIGNES_MODELE:
        return []
    reference = {
        x: tuple(
            median(pages[p][x][i] for p in exemplaires if x in pages.get(p, {}))
            for i in (0, 1)
        )
        for x in modele
    }
    decalages = {}
    for p, lignes in pages.items():
        communes = [x for x in lignes if x in modele]
        if len(communes) >= LIGNES_MODELE:
            decalages[p] = tuple(
                median(lignes[x][i] - reference[x][i] for x in communes) for i in (0, 1)
            )
    relatifs = [
        {
            **r,
            "x0": r["x0"] - decalages[r["page"]][0],
            "y0": r["y0"] - decalages[r["page"]][1],
            "x1": r["x1"] - decalages[r["page"]][0],
            "y1": r["y1"] - decalages[r["page"]][1],
        }
        for r in groupe
        if r["page"] in decalages
    ]
    reperes = []
    for zone in zones(relatifs):
        appris = {r["page"] for r in relatifs if recouvrement(r, zone) > 0}
        for p, (dx, dy) in sorted(decalages.items()):
            reperes.append(
                {
                    "page": p,
                    "x0": round(max(0.0, zone["x0"] + dx), 1),
                    "y0": round(max(0.0, zone["y0"] + dy), 1),
                    "x1": round(zone["x1"] + dx, 1),
                    "y1": round(zone["y1"] + dy, 1),
                    "etiquette": zone["etiquette"],
                    "source": "modèle appris" if p in appris else "modèle",
                }
            )
    return reperes
