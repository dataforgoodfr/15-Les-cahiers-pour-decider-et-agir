"""Sous-thèmes des contributions, repérés par mots-clés (issue #24).

Les sept thèmes et leurs sous-thèmes viennent du document de l'association
« Thématiques » (V2, 8 thèmes et 42 sous-thèmes), le huitième étant ses
thèmes complémentaires (code `2`). S'y ajoutent quelques sujets de 2019
qu'il ne cite pas (marqués `AJOUTS`), pour vérifier sur le corpus s'ils
manquent. Un sous-thème peut relever de plusieurs thèmes : on classe par
sous-thème et on remonte aux thèmes.

Les motifs portent sur le texte normalisé (`normaliser` : minuscules, sans
accents ni ponctuation). C'est un premier repérage, pour mesurer la place
de chaque sous-thème, pas un classement : un mot peut apparaître sans que le
sujet soit traité. Le texte ne sort jamais, seulement des comptes.
"""

import re
import unicodedata

THEMES = {
    "D": "Démocratie",
    "F": "Fiscalité (justice fiscale)",
    "A": "Administration et services publics",
    "H": "Habitabilité et transitions",
    "P": "Pouvoir d'achat",
    "R": "Ruralité",
    "L": "Liens sociaux",
    "2": "Thèmes complémentaires",
    "+": "Hors liste de l'association (à vérifier)",
}

# (sous-thème, thèmes, motifs)
SOUS_THEMES = [
    # Démocratie
    (
        "Meilleure représentativité",
        "D",
        [
            r"\bproportionnel",
            r"\brepresentativite\b",
            r"\bnombre (de|des) (deputes|senateurs|parlementaires|elus)\b",
            r"\bsupprim\w* (le )?senat\b",
            r"\bcese\b",
        ],
    ),
    (
        "Place des citoyens et de leur parole",
        "D",
        [
            r"\bdemocratie (participative|directe)\b",
            r"\btirage au sort\b",
            r"\b(assemblees?|conventions?) citoyennes?\b",
            r"\b(consult|ecout)\w* (le peuple|les citoyens|la population)\b",
            r"\breferendums?\b",
        ],
    ),
    (
        "Place, rôle et profils des élus",
        "D",
        [
            r"\bprivileges?\b",
            r"\b(indemnites?|salaires?|retraites?|avantages) (des|de nos) (elus|deputes|senateurs|ministres|parlementaires)\b",
            r"\banciens presidents\b",
            r"\bcorruption\b",
            r"\bcasier judiciaire\b",
            r"\bineligib",
            r"\bconflits? d interets?\b",
            r"\bcumul (des|de) mandats?\b",
        ],
    ),
    ("RIC", "D", [r"\bric\b", r"referendums? d initiative (citoyenne|populaire)"]),
    (
        "Transformation du système politique",
        "D",
        [
            r"\b(6e|6eme|vie|sixieme) republique\b",
            r"\bconstitution",
            r"\b(quinquennat|septennat)\b",
            r"\bmonarchie (presidentielle|republicaine)\b",
        ],
    ),
    (
        "Vote blanc et nul",
        "D",
        [r"\bvotes? blancs?\b", r"\bvotes? nuls?\b", r"\bbulletins? blancs?\b"],
    ),
    # Fiscalité
    (
        "Diminution des taxes",
        "F",
        [
            r"\b(baiss|diminu|redui|reduct|supprim)\w* (des |les |la |de la )?(taxes?|impots?|tva|csg|prelevements)\b",
            r"\btrop d (impots|taxes)\b",
            r"\b(pression|matraquage) fiscal",
            r"\btaxe d habitation\b",
        ],
    ),
    (
        "Meilleure répartition de l'impôt",
        "F",
        [
            r"\btva\b",
            r"\bcsg\b",
            r"\bimpots? sur le revenu\b",
            r"\btranches? d imposition\b",
            r"\bniches? fiscales?\b",
            r"\bprogressivite\b",
        ],
    ),
    (
        "Rétablissement de l'ISF",
        "F",
        [
            r"\bisf\b",
            r"\bimpot sur la fortune\b",
            r"\bgrandes? fortunes?\b",
            r"\bplus riches\b",
        ],
    ),
    (
        "Lutte contre la fraude fiscale",
        "F",
        [
            r"\b(evasion|fraude|optimisation) fiscale\b",
            r"\bparadis fiscaux\b",
            r"\bexil fiscal\b",
        ],
    ),
    (
        "Taxation financière",
        "F",
        [
            r"\bdividendes?\b",
            r"\btransactions? financieres?\b",
            r"\btaxe (tobin|zucman)\b",
            r"\bspeculat",
            r"\bgafa\b",
        ],
    ),
    # Administration et services publics
    (
        "Décentralisation, ville et campagne",
        "A",
        [
            r"\bdecentralis",
            r"\bcollectivites? (locales|territoriales)\b",
            r"\bmetropoles?\b",
            r"\bintercommunalit",
            r"\bvilles? et (la |les )?campagnes?\b",
        ],
    ),
    (
        "Sécurité et forces de l'ordre",
        "A",
        [
            r"\bforces de l ordre\b",
            r"\bpolic(e|iers?)\b",
            r"\bgendarm",
            r"\binsecurite\b",
            r"\bdelinquan",
            r"\bincivilites?\b",
        ],
    ),
    (
        "Qualité des services publics et de l'information",
        "A",
        [
            r"\bqualite (des|du) services?\b",
            r"\bmedias?\b",
            r"\bjournalis",
            r"\b(fake news|fausses informations)\b",
        ],
    ),
    (
        "Rationaliser, mille-feuille administratif",
        "A",
        [
            r"\bmille ?feuilles?\b",
            r"\btrain de vie\b",
            r"\bdepenses? publiques?\b",
            r"\bgaspillages?\b",
            r"\bbureaucrat",
            r"\bsimplifi\w* (administrati|les demarches)",
        ],
    ),
    (
        "Fin des privatisations",
        "A",
        [r"\bprivatis", r"\bautoroutes?\b", r"\bnationalis"],
    ),
    (
        "Renforcement du service public",
        "A",
        [r"\bservices? publics?\b", r"\bhopita(l|ux)\b", r"\burgences\b"],
    ),
    (
        "École, égalité d'accès",
        "A",
        [
            r"\becoles?\b",
            r"\beducation\b",
            r"\benseignants?\b",
            r"\bprofesseurs?\b",
            r"\b(colleges?|lycees?)\b",
        ],
    ),
    # Habitabilité et transitions
    (
        "Écologie",
        "H",
        [
            r"\bclimat",
            r"\brechauffement\b",
            r"\btransition ecologique\b",
            r"\becologi",
            r"\bdechets?\b",
            r"\bplastiques?\b",
            r"\brecycl",
        ],
    ),
    (
        "Modèle agricole",
        "H",
        [r"\bagricult", r"\bpesticides?\b", r"\bglyphosate\b", r"\bpaysans?\b"],
    ),
    (
        "Soin du vivant, santé et biodiversité",
        "H",
        [
            r"\bbiodiversite\b",
            r"\bpollution",
            r"\bperturbateurs? endocriniens?\b",
            r"\b(bien etre|souffrance|cause) animal",
        ],
    ),
    (
        "Modèle économique",
        "H",
        [
            r"\b(re|de)localis",
            r"\bempreinte carbone\b",
            r"\bmondialisation\b",
            r"\blibre echange\b",
            r"\b(ceta|mercosur)\b",
        ],
    ),
    (
        "Transition énergétique",
        "H",
        [
            r"\btransition energetique\b",
            r"\bnucleaire\b",
            r"\benergies? renouvelables?\b",
            r"\beoliennes?\b",
            r"\b(solaire|photovoltai)",
            r"\b(isolation|renovation) (thermique|energetique|des logements)\b",
        ],
    ),
    (
        "Qualité de l'eau",
        "H",
        [
            r"\bqualite de l eau\b",
            r"\beau potable\b",
            r"\bnappes? phreatiques?\b",
            r"\bassainissement\b",
            r"\bprix de l eau\b",
            r"\bnitrates?\b",
        ],
    ),
    # Pouvoir d'achat
    (
        "Salaires et retraites",
        "P",
        [
            r"\bpouvoir d achat\b",
            r"\bsmic\b",
            r"\bsalaire minimum\b",
            r"\bfins? de mois\b",
            r"\bretraites?\b",
            r"\bpensions?\b",
        ],
    ),
    (
        "Logement",
        "P",
        [r"\blogements?\b", r"\bloyers?\b", r"\bhlm\b", r"\bsans abris?\b", r"\bsdf\b"],
    ),
    (
        "Mobilité, carburant",
        "P",
        [
            r"\bcarburants?\b",
            r"\bessence\b",
            r"\bgasoil\b",
            r"\bgazole\b",
            r"\btaxe carbone\b",
            r"\bticpe\b",
            r"\b80 ?km",
            r"\blimitation de vitesse\b",
            r"\bradars?\b",
            r"\bpeages?\b",
        ],
    ),
    (
        "Justice sociale",
        "P",
        [
            r"\bjustice sociale\b",
            r"\binegalites?\b",
            r"\bprecarite\b",
            r"\bpauvrete\b",
            r"\bminima sociaux\b",
            r"\brsa\b",
        ],
    ),
    (
        "Sécurité sociale alimentaire",
        "P",
        [
            r"\balimentation\b",
            r"\bse nourrir\b",
            r"\bbanques? alimentaires?\b",
            r"\bsecurite sociale (de l )?aliment",
            r"\bcantines?\b",
        ],
    ),
    # Ruralité
    (
        "Accès aux services publics et à la santé",
        "R",
        [
            r"\bmedecins?\b",
            r"\bdeserts? medica",
            r"\bspecialistes\b",
            r"\bmaternites?\b",
            r"\bbureaux? de poste\b",
            r"\btresoreries?\b",
            r"\bfermetures? (des|de|du) (services?|ecoles?|classes?|bureaux?|gares?|maternites?|hopitaux|hopital)\b",
        ],
    ),
    (
        "Mode de vie rural",
        "R",
        [
            r"\bruralite\b",
            r"\b(monde|milieu) rural\b",
            r"\b(zones?|communes?) rurales?\b",
            r"\bterritoires? ruraux\b",
            r"\bvillages?\b",
        ],
    ),
    (
        "Local et petits producteurs",
        "R",
        [
            r"\bpetits? producteurs?\b",
            r"\bcircuits? courts?\b",
            r"\bproduits? locaux\b",
            r"\b(petits? commerces?|commerces? de proximite)\b",
            r"\bconsommer local\b",
        ],
    ),
    (
        "Transports en commun",
        "RAHP",
        [r"\btransports? (en commun|publics?|collectifs?)\b"],
    ),
    (
        "Trains, fermeture de lignes",
        "R",
        [
            r"\bsncf\b",
            r"\bpetites? lignes\b",
            r"\blignes? (de train|ferroviaires?|secondaires)\b",
            r"\btrains?\b",
            r"\bgares?\b",
        ],
    ),
    # Liens sociaux
    (
        "Liens sociaux, vivre ensemble",
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
    # Thèmes complémentaires de l'association
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
        "2A",
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
    ("Chômage, emploi", "+P", [r"\bchomage\b", r"\bchomeurs?\b", r"\bpole emploi\b"]),
    (
        "Personnes âgées, EHPAD",
        "+A",
        [
            r"\behpad\b",
            r"\bmaisons? de retraite\b",
            r"\bdependance\b",
            r"\bpersonnes? agees\b",
        ],
    ),
    ("Handicap", "+A", [r"\bhandicap"]),
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
