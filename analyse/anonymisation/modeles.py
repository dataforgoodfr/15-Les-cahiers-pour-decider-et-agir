"""Données personnelles repérées par un modèle local (issue #7).

Les règles de `detection` ne voient que la forme des mots ; un modèle lit le
sens : un nom sans civilité, « ma fille, infirmière à l'hôpital de X ». Le
modèle tourne sur cette machine, jamais chez un tiers : les cahiers sont des
opinions politiques signées (RGPD, art. 9).

Deux familles, appelées sur le texte de chaque page :

- `Ollama` : un LLM servi par Ollama en local (Qwen, Gemma…), à qui l'on
  demande la liste des passages qui identifient une personne ;
- `Gliner` : un NER spécialisé données personnelles (dépendances du groupe
  `modeles`).

Un modèle rend des passages de texte ; `localiser` les ramène aux cadres des
mots de la page. Les passages ne sortent pas de ce module, sauf dans le
cache, sous `data/` (hors git).
"""

import json
import re
import urllib.request
from pathlib import Path

from anonymisation.detection import _cadre, _simple

OLLAMA = "http://127.0.0.1:11434"
ETIQUETTES = (
    "nom",
    "prénom",
    "adresse",
    "courriel",
    "téléphone",
    "autre donnée identifiante",
)
CONSIGNE = """\
Voici le texte d'une page d'un cahier citoyen de 2019 (OCR, avec des fautes).
Relève chaque passage qui permet d'identifier une personne privée : nom,
prénom, adresse postale, courriel, téléphone, et toute autre donnée
identifiante (date de naissance, profession avec un lieu précis, lien de
parenté avec une personne nommée, numéro de dossier…).
Recopie chaque passage exactement comme dans le texte, le plus court possible.
N'inclus pas les personnalités politiques nationales (président, ministres)
ni les noms de communes ou d'institutions seuls. Dans le doute, inclus le
passage. S'il n'y a rien, rends une liste vide.

Texte :
"""
SCHEMA = {
    "type": "object",
    "properties": {
        "donnees": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "type": {"type": "string", "enum": list(ETIQUETTES)},
                },
                "required": ["texte", "type"],
            },
        }
    },
    "required": ["donnees"],
}
# étiquettes GLiNER (anglais, modèle multilingue) -> étiquettes de l'outil d'annotation
GLINER = {
    "person": "nom",
    "email": "courriel",
    "phone number": "téléphone",
    "address": "adresse",
    "date of birth": "autre donnée identifiante",
    "social security number": "autre donnée identifiante",
}
SEUIL_GLINER = 0.3  # bas : on préfère un repérage de trop
# unités (mots, signes) par morceau : la fenêtre du modèle en lit 384 et
# ignore la suite ; une ligne trop longue est coupée, avec un chevauchement
# pour ne pas trancher un nom
LONGUEUR_GLINER = 300
CHEVAUCHEMENT_GLINER = 20
UNITE = re.compile(r"\w+(?:[-_.']\w+)*|\S")


def texte_de_la_page(mots: list[tuple]) -> str:
    """Le texte de la page, une ligne de la couche texte par ligne."""
    lignes: dict[tuple, list] = {}
    for m in mots:
        lignes.setdefault((m[5], m[6]), []).append(m)
    return "\n".join(
        " ".join(m[4] for m in sorted(ligne, key=lambda m: m[7]))
        for ligne in lignes.values()
    )


def localiser(passages: list[tuple[str, str]], mots: list[tuple]) -> list[dict]:
    """Cadres des mots couverts par chaque passage (texte, étiquette).

    La comparaison ignore la casse, les accents, la ponctuation et les
    espaces (« Jean-Paul » de l'OCR et « jean paul » du modèle se valent),
    mais le passage commence et finit sur une limite de mot : « Dupont » ne
    couvre pas « Duponteau ». Un passage qui revient plusieurs fois sur la
    page est repéré partout. Un cadre par ligne couverte.
    """
    simples = [_simple(m[4]) for m in mots]
    flux, rangs, debuts, fins = "", [], set(), set()
    for i, simple in enumerate(simples):
        debuts.add(len(flux))
        flux += simple
        rangs += [i] * len(simple)
        fins.add(len(flux))
    reperes = []
    for passage, etiquette in passages:
        cible = _simple(passage)
        if len(cible) < 2:
            continue
        for t in re.finditer(f"(?={re.escape(cible)})", flux):
            debut, fin = t.start(), t.start() + len(cible)
            if debut not in debuts or fin not in fins:
                continue
            couverts = [mots[i] for i in range(rangs[debut], rangs[fin - 1] + 1)]
            # « cle » : comme pour les règles, compte les cahiers où revient
            # un nom ; retirée par `retirer_repandues`
            reperes += [r | {"cle": cible} for r in _par_ligne(couverts, etiquette)]
    return reperes


def _par_ligne(couverts: list[tuple], etiquette: str) -> list[dict]:
    lignes: dict[tuple, list] = {}
    for m in couverts:
        lignes.setdefault((m[5], m[6]), []).append(m)
    return [
        _cadre(
            min(m[0] for m in ligne),
            min(m[1] for m in ligne),
            max(m[2] for m in ligne),
            max(m[3] for m in ligne),
            etiquette,
        )
        for ligne in lignes.values()
    ]


class Ollama:
    """Un LLM servi par Ollama sur cette machine."""

    def __init__(self, modele: str, url: str = OLLAMA):
        if not url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("le modèle doit tourner sur cette machine")
        self.nom = f"ollama:{modele}"
        self.modele = modele
        self.url = url

    def __call__(self, texte: str) -> list[tuple[str, str]]:
        corps = {
            "model": self.modele,
            "prompt": CONSIGNE + texte,
            "format": SCHEMA,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        requete = urllib.request.Request(
            f"{self.url}/api/generate",
            data=json.dumps(corps).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(requete, timeout=600) as reponse:
            sortie = json.load(reponse)["response"]
        try:
            donnees = json.loads(sortie)["donnees"]
        except json.JSONDecodeError, KeyError, TypeError:
            return []
        return [
            (d["texte"], d["type"] if d.get("type") in ETIQUETTES else ETIQUETTES[-1])
            for d in donnees
            if isinstance(d, dict) and isinstance(d.get("texte"), str)
        ]


class Gliner:
    """NER de données personnelles (GLiNER), sur CPU."""

    def __init__(self, modele: str = "urchade/gliner_multi_pii-v1"):
        from gliner import GLiNER

        self.nom = f"gliner:{modele}"
        self.ner = GLiNER.from_pretrained(modele)

    def __call__(self, texte: str) -> list[tuple[str, str]]:
        passages = []
        for morceau in _morceaux(texte, LONGUEUR_GLINER):
            for e in self.ner.predict_entities(
                morceau, list(GLINER), threshold=SEUIL_GLINER
            ):
                passages.append((e["text"], GLINER[e["label"]]))
        return passages


def _morceaux(
    texte: str, longueur: int, chevauchement: int = CHEVAUCHEMENT_GLINER
) -> list[str]:
    """Coupe aux fins de ligne, en morceaux d'au plus `longueur` unités
    (mots ou signes). Une ligne plus longue est coupée en tronçons qui se
    chevauchent de `chevauchement` unités."""
    morceaux, courant, taille = [], "", 0
    for ligne in texte.split("\n"):
        unites = list(UNITE.finditer(ligne))
        if len(unites) > longueur:
            if courant:
                morceaux.append(courant)
                courant, taille = "", 0
            pas = longueur - chevauchement
            for k in range(0, len(unites) - chevauchement, pas):
                tron = unites[k : k + longueur]
                morceaux.append(ligne[tron[0].start() : tron[-1].end()] + "\n")
            continue
        if courant and taille + len(unites) > longueur:
            morceaux.append(courant)
            courant, taille = "", 0
        courant += ligne + "\n"
        taille += len(unites)
    return [*morceaux, courant] if courant else morceaux


def charger(nom: str):
    """`ollama:qwen3.5:9b` ou `gliner[:identifiant]`."""
    famille, _, modele = nom.partition(":")
    if famille == "ollama" and modele:
        return Ollama(modele)
    if famille == "gliner":
        return Gliner(modele) if modele else Gliner()
    raise ValueError(f"modèle inconnu : {nom}")


class Cache:
    """Passages déjà rendus par un modèle, par (fichier, page). Contient du
    texte des cahiers : sous `data/`, jamais dans git, jamais affiché."""

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.passages: dict[tuple, list] = {}
        if chemin.exists():
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                e = json.loads(ligne)
                self.passages[e["fichier"], e["page"]] = [
                    tuple(p) for p in e["passages"]
                ]

    def obtenir(self, fichier: str, page: int, modele, texte: str) -> list:
        cle = (fichier, page)
        if cle not in self.passages:
            self.passages[cle] = modele(texte)
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                e = {"fichier": fichier, "page": page, "passages": self.passages[cle]}
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return self.passages[cle]
