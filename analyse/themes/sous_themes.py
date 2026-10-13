"""Sous-thèmes des contributions, repérés par mots-clés (issue #24).

Les cinq thèmes et leurs sous-thèmes viennent du document de l'association
« Corpus et thèmes des cahiers » (V2) ; s'y ajoutent ses thèmes secondaires,
et quelques sujets de 2019 qu'il ne cite pas (marqués `AJOUTS`), pour
vérifier sur le corpus s'ils manquent. Un sous-thème peut relever de
plusieurs thèmes : on classe par sous-thème et on remonte aux thèmes.

Les motifs portent sur le texte normalisé (`normaliser` : minuscules, sans
accents ni ponctuation). C'est un premier repérage, pour mesurer la place
de chaque sous-thème, pas un classement : un mot peut apparaître sans que le
sujet soit traité. Le texte ne sort jamais, seulement des comptes.
"""

import re
import unicodedata

THEMES = {
    "D": "Démocratie",
    "J": "Justice fiscale et sociale",
    "S": "Services publics et égalité des territoires",
    "E": "Écologie solidaire et accessible à tous",
    "L": "Liens sociaux, vivre ensemble",
    "2": "Thèmes secondaires",
    "+": "Hors liste de l'association (à vérifier)",
}

# (sous-thème, thèmes, motifs)
SOUS_THEMES = [
    # Démocratie
    ("RIC", "D", [r"\bric\b", r"referendums? d initiative (citoyenne|populaire)"]),
    ("Référendum (tous)", "D", [r"\breferendums?\b"]),
    (
        "Vote blanc et nul",
        "D",
        [r"\bvotes? blancs?\b", r"\bvotes? nuls?\b", r"\bbulletins? blancs?\b"],
    ),
    (
        "Privilèges et rémunération des élus",
        "D",
        [
            r"\bprivileges?\b",
            r"\b(indemnites?|salaires?|retraites?|avantages) (des|de nos) (elus|deputes|senateurs|ministres|parlementaires)\b",
            r"\banciens presidents\b",
        ],
    ),
    (
        "Exemplarité des élus",
        "D",
        [
            r"\bcorruption\b",
            r"\bcasier judiciaire\b",
            r"\bineligib",
            r"\bconflits? d interets?\b",
        ],
    ),
    ("Proportionnelle", "D", [r"\bproportionnel"]),
    (
        "Nombre de parlementaires, Sénat",
        "D",
        [
            r"\bnombre (de|des) (deputes|senateurs|parlementaires|elus)\b",
            r"\bsupprim\w* (le )?senat\b",
            r"\bcese\b",
        ],
    ),
    (
        "Participation citoyenne",
        "D",
        [
            r"\bdemocratie (participative|directe)\b",
            r"\btirage au sort\b",
            r"\b(assemblees?|conventions?) citoyennes?\b",
        ],
    ),
    # Justice fiscale et sociale
    (
        "Pouvoir d'achat, salaires",
        "J",
        [
            r"\bpouvoir d achat\b",
            r"\bsmic\b",
            r"\bsalaire minimum\b",
            r"\bfins? de mois\b",
        ],
    ),
    (
        "ISF, grandes fortunes",
        "J",
        [
            r"\bisf\b",
            r"\bimpot sur la fortune\b",
            r"\bgrandes? fortunes?\b",
            r"\bplus riches\b",
        ],
    ),
    (
        "Évasion et fraude fiscales",
        "J",
        [
            r"\b(evasion|fraude|optimisation) fiscale\b",
            r"\bparadis fiscaux\b",
            r"\bexil fiscal\b",
        ],
    ),
    (
        "Taxation financière",
        "J",
        [
            r"\bdividendes?\b",
            r"\btransactions? financieres?\b",
            r"\btaxe tobin\b",
            r"\bspeculat",
        ],
    ),
    (
        "Impôts, TVA, CSG",
        "J",
        [
            r"\btva\b",
            r"\bcsg\b",
            r"\bimpots? sur le revenu\b",
            r"\btranches? d imposition\b",
            r"\bniches? fiscales?\b",
        ],
    ),
    (
        "Logement",
        "J",
        [r"\blogements?\b", r"\bloyers?\b", r"\bhlm\b", r"\bsans abris?\b", r"\bsdf\b"],
    ),
    (
        "Alimentation",
        "J",
        [r"\balimentation\b", r"\bse nourrir\b", r"\bbanques? alimentaires?\b"],
    ),
    # Services publics et égalité des territoires
    (
        "Services publics de proximité",
        "S",
        [
            r"\bservices? publics?\b",
            r"\bbureaux? de poste\b",
            r"\btresoreries?\b",
            r"\bfermetures? (des|de|du) (services?|ecoles?|classes?|bureaux?|gares?|maternites?|hopitaux|hopital)\b",
        ],
    ),
    (
        "Santé, médecins, hôpital",
        "S",
        [
            r"\bmedecins?\b",
            r"\bdeserts? medica",
            r"\bhopita(l|ux)\b",
            r"\burgences\b",
            r"\bmaternites?\b",
        ],
    ),
    (
        "École, éducation",
        "S",
        [
            r"\becoles?\b",
            r"\beducation\b",
            r"\benseignants?\b",
            r"\bprofesseurs?\b",
            r"\b(colleges?|lycees?)\b",
        ],
    ),
    (
        "Transports en commun, trains",
        "SE",
        [
            r"\btransports? (en commun|publics?|collectifs?)\b",
            r"\bsncf\b",
            r"\bpetites? lignes\b",
            r"\blignes? (de train|ferroviaires?|secondaires)\b",
            r"\btrains?\b",
        ],
    ),
    # Écologie
    (
        "Climat, transition écologique",
        "E",
        [
            r"\bclimat",
            r"\brechauffement\b",
            r"\btransition (ecologique|energetique)\b",
            r"\becologi",
        ],
    ),
    (
        "Carburant, taxe carbone",
        "EJ",
        [
            r"\bcarburants?\b",
            r"\bgasoil\b",
            r"\bgazole\b",
            r"\btaxe carbone\b",
            r"\bticpe\b",
        ],
    ),
    # Liens sociaux
    (
        "Isolement, liens sociaux",
        "L",
        [
            r"\bisolement\b",
            r"\bsolitude\b",
            r"\bliens? sociaux\b",
            r"\blien social\b",
            r"\bvivre ensemble\b",
            r"\bmepris\b",
        ],
    ),
    # Thèmes secondaires de l'association
    (
        "Égalité femmes-hommes",
        "2",
        [r"\begalite (hommes? femmes?|femmes? hommes?|salariale)\b", r"\bparite\b"],
    ),
    (
        "Violences sexuelles et conjugales",
        "2",
        [
            r"\bviolences? (sexuelles?|conjugales?|faites aux femmes)\b",
            r"\bfeminicides?\b",
        ],
    ),
    (
        "Répression, violences policières",
        "2",
        [
            r"\bviolences? policieres?\b",
            r"\brepression\b",
            r"\blbd\b",
            r"\bflash ?ball\b",
        ],
    ),
    (
        "Fin de vie",
        "2",
        [
            r"\bfin de vie\b",
            r"\beuthanasie\b",
            r"\bmourir dans la dignite\b",
            r"\bsuicide assiste\b",
        ],
    ),
    ("Contrôle des lobbies", "2D", [r"\blobb(y|ies|ying|ys|is)\b"]),
    (
        "Fraude sociale, assistanat",
        "2",
        [
            r"\bassistanat\b",
            r"\bassistes\b",
            r"\bfraude sociale\b",
            r"\ballocations indues\b",
        ],
    ),
    (
        "Illectronisme, numérique",
        "2S",
        [
            r"\billectronisme\b",
            r"\bnumerique\b",
            r"\bdematerialis",
            r"\binternet\b",
            r"\bzones? blanches?\b",
        ],
    ),
]

AJOUTS = [
    ("Retraites et pensions", "+J", [r"\bretraites?\b", r"\bpensions?\b"]),
    ("Chômage, emploi", "+J", [r"\bchomage\b", r"\bchomeurs?\b", r"\bpole emploi\b"]),
    (
        "80 km/h, radars",
        "+E",
        [r"\b80 ?km", r"\blimitation de vitesse\b", r"\bradars?\b"],
    ),
    (
        "Énergie, nucléaire",
        "+E",
        [r"\bnucleaire\b", r"\benergies? renouvelables?\b", r"\beoliennes?\b"],
    ),
    (
        "Agriculture, pesticides",
        "+E",
        [r"\bagricult", r"\bpesticides?\b", r"\bglyphosate\b", r"\bpaysans?\b"],
    ),
    ("Déchets, plastique", "+E", [r"\bdechets?\b", r"\bplastiques?\b", r"\brecycl"]),
    (
        "Personnes âgées, EHPAD",
        "+S",
        [
            r"\behpad\b",
            r"\bmaisons? de retraite\b",
            r"\bdependance\b",
            r"\bpersonnes? agees\b",
        ],
    ),
    ("Handicap", "+S", [r"\bhandicap"]),
    (
        "Train de vie de l'État",
        "+D",
        [r"\btrain de vie\b", r"\bdepenses? publiques?\b", r"\bgaspillages?\b"],
    ),
    (
        "Immigration",
        "+",
        [
            r"\bimmigr",
            r"\bmigrants?\b",
            r"\bdroit d asile\b",
            r"\bregroupement familial\b",
        ],
    ),
    ("Europe", "+", [r"\beurope", r"\bbruxelles\b"]),
    (
        "Insécurité, délinquance",
        "+",
        [r"\binsecurite\b", r"\bdelinquan", r"\bincivilites?\b"],
    ),
    ("Laïcité, religion", "+", [r"\blaicite\b", r"\breligi"]),
]

TOUS = SOUS_THEMES + AJOUTS
_MOTIFS = [(nom, re.compile("|".join(motifs))) for nom, _, motifs in TOUS]


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ; la ponctuation devient une espace."""
    texte = unicodedata.normalize("NFKD", texte.lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


def sous_themes(texte: str) -> set[str]:
    """Les sous-thèmes dont un motif apparaît dans le texte."""
    texte = normaliser(texte)
    return {nom for nom, motif in _MOTIFS if motif.search(texte)}
