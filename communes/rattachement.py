"""Rattachement des codes INSEE du corpus aux variables des communes.

Le référentiel est celui du 1er janvier 2019 : les codes des noms de fichiers
ont été attribués au moment du dépôt des cahiers (février-avril 2019), et des
communes ont fusionné depuis. Un référentiel plus récent en perdrait certaines,
ou leur prêterait la population de la commune nouvelle.

La grille de densité n'est pas publiée dans la géographie de 2019 : on prend
celle de 2021 et on y passe par les mouvements de communes. Quand le code
change en route, la colonne `note` le dit.
"""

from dataclasses import dataclass, field

from communes import sources

# Types d'entité du COG
COMMUNE = "COM"
DELEGUEE = "COMD"
ASSOCIEE = "COMA"
ARRONDISSEMENT = "ARM"
# Quand un code figure sous plusieurs types (une commune nouvelle garde souvent
# le code de son chef-lieu, qui devient aussi commune déléguée), la commune de
# plein exercice l'emporte.
PRIORITE = {COMMUNE: 0, ARRONDISSEMENT: 1, DELEGUEE: 2, ASSOCIEE: 3}

PIVOT = "2019-01-01"
GEOGRAPHIE_GRILLE = "2021-01-01"
# Le système de dépôt travaillait parfois sur le COG 2018 : un code supprimé au
# 1er janvier 2019 désigne encore une commune réelle, qu'on suit jusqu'à la
# commune nouvelle. Un code disparu avant 2018 n'est pas suivi.
DEBUT_COG_PERIME = "2018-01-02"

DENSITE = {
    1: "densément peuplée",
    2: "densité intermédiaire",
    3: "peu dense",
    4: "très peu dense",
}

COLONNES = [
    "nom_2019",
    "type_2019",
    "commune_parente",
    "departement",
    "nom_departement",
    "region",
    "nom_region",
    "population_2017",
    "population_incluse_dans",
    "code_grille",
    "densite",
    "libelle_densite",
    "espace",
    "note",
]


@dataclass
class Referentiel:
    """Les tables de l'INSEE nécessaires au rattachement, indexées par code."""

    cog: dict[str, dict[str, str]]
    departements: dict[str, str]
    regions: dict[str, str]
    populations: dict[str, int]
    grille: dict[str, int]
    # mouvements indexés par code d'origine, triés par date
    mouvements: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    @classmethod
    def depuis_lignes(
        cls,
        communes: list[dict[str, str]],
        departements: list[dict[str, str]],
        regions: list[dict[str, str]],
        populations: list[dict[str, str]],
        grille: dict[str, int],
        mouvements: list[dict[str, str]],
    ) -> Referentiel:
        cog: dict[str, dict[str, str]] = {}
        for ligne in communes:
            code = ligne["com"]
            actuelle = cog.get(code)
            if (
                actuelle is None
                or PRIORITE[ligne["typecom"]] < PRIORITE[actuelle["typecom"]]
            ):
                cog[code] = ligne
        pop: dict[str, int] = {}
        for ligne in populations:
            # Communes.csv est lu en premier : sa ligne de plein exercice reste
            # la bonne quand une commune déléguée porte le même code.
            pop.setdefault(ligne["DEPCOM"].strip(), int(ligne["PMUN"]))
        # Paris, Lyon et Marseille n'ont de ligne que par arrondissement municipal
        arrondissements: dict[str, int] = {}
        for code, ligne in cog.items():
            if ligne["typecom"] == ARRONDISSEMENT and code in pop:
                parente = ligne["comparent"]
                arrondissements[parente] = arrondissements.get(parente, 0) + pop[code]
        for parente, total in arrondissements.items():
            pop.setdefault(parente, total)
        index: dict[str, list[dict[str, str]]] = {}
        for m in sorted(mouvements, key=lambda m: m["DATE_EFF"]):
            index.setdefault(m["COM_AV"], []).append(m)
        return cls(
            cog=cog,
            departements={d["dep"]: d["libelle"] for d in departements},
            regions={r["reg"]: r["libelle"] for r in regions},
            populations=pop,
            grille=grille,
            mouvements=index,
        )

    @classmethod
    def telecharger(cls, cache) -> Referentiel:
        contenu = sources.telecharger(sources.POPULATIONS, cache)
        populations = []
        for fichier in ("Communes.csv", "Communes_associees_ou_deleguees.csv"):
            populations += sources.lignes_csv(sources.membre_zip(contenu, fichier), ";")
        mouvements = sources.telecharger(sources.MOUVEMENTS, cache).decode("utf-8")
        return cls.depuis_lignes(
            communes=sources.premier_csv_zip(
                sources.telecharger(sources.COG_COMMUNES, cache)
            ),
            departements=sources.premier_csv_zip(
                sources.telecharger(sources.COG_DEPARTEMENTS, cache)
            ),
            regions=sources.premier_csv_zip(
                sources.telecharger(sources.COG_REGIONS, cache)
            ),
            populations=populations,
            grille=sources.grille_densite(
                sources.telecharger(sources.GRILLE_DENSITE, cache)
            ),
            mouvements=sources.lignes_csv(mouvements),
        )

    def suivre(
        self, code: str, debut: str, fin: str
    ) -> tuple[str, list[dict[str, str]]]:
        """Suit les fusions et changements de code d'une commune entre deux dates.

        Returns:
            Le code d'arrivée (le code de départ s'il n'a pas bougé) et les
            mouvements suivis.
        """
        chaine = []
        vus = {code}
        while True:
            suite = [
                m
                for m in self.mouvements.get(code, [])
                if debut <= m["DATE_EFF"] <= fin
                and m["TYPECOM_AP"] == COMMUNE
                and m["COM_AP"] not in vus
                and (not chaine or m["DATE_EFF"] >= chaine[-1]["DATE_EFF"])
            ]
            if not suite:
                return code, chaine
            mouvement = suite[0]
            chaine.append(mouvement)
            code = mouvement["COM_AP"]
            vus.add(code)


def _decrire(mouvement: dict[str, str]) -> str:
    return (
        f"{mouvement['LIBELLE_AV']} ({mouvement['COM_AV']}) → "
        f"{mouvement['LIBELLE_AP']} ({mouvement['COM_AP']}) le {mouvement['DATE_EFF']}"
    )


def raison_non_rattache(code: str, ref: Referentiel) -> str:
    if code == "00000":
        return "commune non renseignée à la source"
    if code.startswith(("975", "977", "978", "98", "99")):
        return "hors du COG des communes (collectivité d'outre-mer ou étranger)"
    if code in ref.mouvements:
        return "code disparu avant 2018 : " + _decrire(ref.mouvements[code][-1])
    return "code inconnu du COG"


def rattacher(code: str, ref: Referentiel) -> dict[str, str] | None:
    """Variables de la commune pour un code du corpus, ou None si non rattachable."""
    notes = []
    ligne = ref.cog.get(code)
    if ligne is None:
        # Code déjà supprimé au 1er janvier 2019 : on suit jusqu'à la commune nouvelle
        arrivee, chaine = ref.suivre(code, DEBUT_COG_PERIME, PIVOT)
        if not chaine or arrivee not in ref.cog:
            return None
        notes.append("code supprimé avant les cahiers : " + _decrire(chaine[-1]))
        nouvelle = ref.cog[arrivee]
        ligne = {
            "typecom": "supprimée",
            "libelle": chaine[0]["LIBELLE_AV"],
            "comparent": arrivee,
            "dep": nouvelle["dep"],
            "reg": nouvelle["reg"],
        }

    type_ = ligne["typecom"]
    parente = ligne.get("comparent", "")
    if not ligne["dep"] and parente:
        # Les communes déléguées et associées n'ont ni département ni région dans le COG
        ligne = {
            **ligne,
            "dep": ref.cog[parente]["dep"],
            "reg": ref.cog[parente]["reg"],
        }

    population = ref.populations.get(code) if type_ != "supprimée" else None
    if population is None and ligne["dep"] == "976":
        notes.append("Mayotte : absente des populations légales millésimées 2017")
    # La population d'une commune déléguée, associée ou d'un arrondissement est
    # comprise dans celle de sa commune parente : ne pas sommer les deux.
    incluse_dans = parente if type_ != COMMUNE else ""

    base = code if type_ == COMMUNE else parente
    code_grille, chaine = ref.suivre(base, "2019-01-02", GEOGRAPHIE_GRILLE)
    if base != code:
        notes.append(f"densité de la commune parente {base}")
    if chaine:
        notes.append("densité de la commune de 2021 : " + _decrire(chaine[-1]))
    densite = ref.grille.get(code_grille)

    return {
        "nom_2019": ligne["libelle"],
        "type_2019": type_,
        "commune_parente": parente,
        "departement": ligne["dep"],
        "nom_departement": ref.departements.get(ligne["dep"], ""),
        "region": ligne["reg"],
        "nom_region": ref.regions.get(ligne["reg"], ""),
        "population_2017": "" if population is None else str(population),
        "population_incluse_dans": incluse_dans,
        "code_grille": code_grille if densite else "",
        "densite": str(densite) if densite else "",
        "libelle_densite": DENSITE.get(densite, ""),
        "espace": "" if not densite else ("urbain" if densite <= 2 else "rural"),
        "note": " ; ".join(notes),
    }
