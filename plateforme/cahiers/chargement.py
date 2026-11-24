"""Logique réutilisable de chargement des référentiels de l'app `cahiers`.

Ce module est indépendant de l'interface CLI des commandes Django afin d'être
facilement testable et appelable depuis d'autres scripts ou commandes
d'orchestration.
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction

from cahiers.models import Thematique

FICHIER_THEMATIQUES_MOCK = (
    settings.BASE_DIR / "cahiers" / "data" / "thematiques_mock.csv"
)

COLONNES_THEMATIQUES = ("theme", "sous_theme", "slug", "ordre", "description")
MOTIF_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ErreurChargement(ValueError):
    """Erreur de validation ou de structure lors d'un chargement de données."""


@dataclass(frozen=True)
class ResultatChargementThematiques:
    """Bilan d'une opération de chargement des thématiques."""

    crees: int
    mises_a_jour: int
    descriptions_preservees: int
    absentes_du_fichier: int

    @property
    def total_fichier(self) -> int:
        return self.crees + self.mises_a_jour


def _valider_lignes_thematiques(fichier: Path) -> tuple[list[dict], list[dict]]:
    """Lit et valide le CSV des thématiques avant toute écriture en base.

    Retourne le couple ``(lignes_themes, lignes_sous_themes)`` normalisé.
    """
    if not fichier.is_file():
        raise ErreurChargement(f"Fichier introuvable : {fichier}")

    with fichier.open(newline="", encoding="utf-8") as handle:
        lecteur = csv.DictReader(handle)
        if lecteur.fieldnames is None or tuple(lecteur.fieldnames) != COLONNES_THEMATIQUES:
            raise ErreurChargement(
                "Colonnes CSV invalides. Attendues : "
                f"{', '.join(COLONNES_THEMATIQUES)} ; "
                f"reçues : {lecteur.fieldnames}."
            )
        lignes = list(lecteur)

    if not lignes:
        raise ErreurChargement(f"Le fichier {fichier} ne contient aucune thématique.")

    slugs_vus: set[str] = set()
    ordres_vus: set[tuple[str | None, int]] = set()
    themes_par_nom: dict[str, str] = {}
    lignes_themes: list[dict] = []
    lignes_sous_themes: list[dict] = []

    for numero_ligne, brute in enumerate(lignes, start=2):
        theme = (brute["theme"] or "").strip()
        sous_theme = (brute["sous_theme"] or "").strip()
        slug = (brute["slug"] or "").strip()
        ordre_brut = (brute["ordre"] or "").strip()
        description = (brute["description"] or "").strip()

        if not theme:
            raise ErreurChargement(f"Ligne {numero_ligne} : colonne 'theme' vide.")
        if not slug or not MOTIF_SLUG.fullmatch(slug):
            raise ErreurChargement(
                f"Ligne {numero_ligne} : slug invalide {slug!r} "
                "(attendu : minuscules ASCII, chiffres et tirets)."
            )
        if slug in slugs_vus:
            raise ErreurChargement(f"Ligne {numero_ligne} : slug en doublon {slug!r}.")
        slugs_vus.add(slug)

        try:
            ordre = int(ordre_brut)
        except ValueError as exc:
            raise ErreurChargement(
                f"Ligne {numero_ligne} : ordre non entier {ordre_brut!r}."
            ) from exc
        if ordre < 1:
            raise ErreurChargement(
                f"Ligne {numero_ligne} : l'ordre doit être supérieur ou égal à 1 ({ordre})."
            )

        cle_ordre = (None if not sous_theme else theme, ordre)
        if cle_ordre in ordres_vus:
            raise ErreurChargement(
                f"Ligne {numero_ligne} : ordre {ordre} en doublon au sein du même niveau."
            )
        ordres_vus.add(cle_ordre)

        entree = {
            "ligne": numero_ligne,
            "theme": theme,
            "sous_theme": sous_theme,
            "slug": slug,
            "ordre": ordre,
            "description": description,
        }
        if not sous_theme:
            if theme in themes_par_nom:
                raise ErreurChargement(
                    f"Ligne {numero_ligne} : thème racine en doublon {theme!r}."
                )
            themes_par_nom[theme] = slug
            lignes_themes.append(entree)
        else:
            lignes_sous_themes.append(entree)

    for entree in lignes_sous_themes:
        if entree["theme"] not in themes_par_nom:
            raise ErreurChargement(
                f"Ligne {entree['ligne']} : thème parent {entree['theme']!r} "
                "absent des thèmes principaux du fichier."
            )

    return lignes_themes, lignes_sous_themes


@transaction.atomic
def charger_thematiques(
    fichier: Path,
    *,
    ecraser_descriptions: bool = False,
) -> ResultatChargementThematiques:
    """Charge ou met à jour la taxonomie de thématiques depuis un fichier CSV.

    Le chargement est idempotent (clé métier = ``slug``) et s'exécute en deux
    passes atomiques (thèmes principaux puis sous-thèmes). Par défaut, toute
    ``description`` déjà renseignée en base est préservée afin de ne pas
    écraser les retouches effectuées dans Wagtail ; passer
    ``ecraser_descriptions=True`` pour forcer l'écrasement depuis le CSV.

    Les éventuelles thématiques déjà présentes en base mais absentes du CSV ne
    sont pas supprimées (respect de ``on_delete=PROTECT``) et sont simplement
    comptabilisées dans le résultat.
    """
    lignes_themes, lignes_sous_themes = _valider_lignes_thematiques(fichier)

    existantes = {
        thematique.slug: thematique for thematique in Thematique.objects.all()
    }
    crees = 0
    mises_a_jour = 0
    descriptions_preservees = 0
    slugs_fichier: set[str] = set()
    themes_par_nom: dict[str, Thematique] = {}

    def _enregistrer(
        *,
        slug: str,
        nom: str,
        parent: Thematique | None,
        ordre: int,
        description_csv: str,
    ) -> Thematique:
        nonlocal crees, mises_a_jour, descriptions_preservees
        slugs_fichier.add(slug)
        existante = existantes.get(slug)
        if existante is None:
            thematique = Thematique(
                slug=slug,
                nom=nom,
                parent=parent,
                ordre=ordre,
                description=description_csv,
            )
            thematique.full_clean(validate_constraints=False)
            thematique.save()
            existantes[slug] = thematique
            crees += 1
            return thematique

        existante.nom = nom
        existante.parent = parent
        existante.ordre = ordre
        if ecraser_descriptions or not existante.description:
            existante.description = description_csv
        elif description_csv and existante.description != description_csv:
            descriptions_preservees += 1

        existante.full_clean(validate_constraints=False)
        existante.save()
        mises_a_jour += 1
        return existante

    # Passe 1 : thèmes principaux (parent=None)
    for entree in lignes_themes:
        thematique = _enregistrer(
            slug=entree["slug"],
            nom=entree["theme"],
            parent=None,
            ordre=entree["ordre"],
            description_csv=entree["description"],
        )
        themes_par_nom[entree["theme"]] = thematique

    # Passe 2 : sous-thèmes rattachés à leur thème principal
    for entree in lignes_sous_themes:
        _enregistrer(
            slug=entree["slug"],
            nom=entree["sous_theme"],
            parent=themes_par_nom[entree["theme"]],
            ordre=entree["ordre"],
            description_csv=entree["description"],
        )

    absentes = sum(1 for slug in existantes if slug not in slugs_fichier)
    return ResultatChargementThematiques(
        crees=crees,
        mises_a_jour=mises_a_jour,
        descriptions_preservees=descriptions_preservees,
        absentes_du_fichier=absentes,
    )
