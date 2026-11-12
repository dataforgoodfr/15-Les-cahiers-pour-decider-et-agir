"""Charge les extraits choisis des transcriptions de Marie-Anne Chabin.

Lit le fichier `cahiers_chabin_extraits.json` et enregistre de manière
idempotente et en masse (`bulk_create`) :
- le `Run` de délimitation correspondant, activé s'il n'y en a pas d'autre,
- les communes citées, si le référentiel n'est pas encore chargé,
- les objets `Document` associés à chaque cahier citoyen,
- les objets `Contribution` contenant le texte des transcriptions,
- un PDF d'extrait par contribution, pour que la page d'accueil ait
  quelque chose à montrer sans les sorties d'`analyse/`.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers import noms
from cahiers.models import Contribution, Document, Run
from territoires.models import Commune, Departement, Region

LIBELLE = "Extraits choisis des transcriptions de Marie-Anne Chabin"
AUTEUR = "Marie-Anne Chabin"

CHAMPS_DOCUMENT = [
    "categorie",
    "mode",
    "code_postal",
    "date_depot",
    "numero",
    "code_insee",
    "commune",
]
CHAMPS_CONTRIBUTION = ["texte", "page_debut", "page_fin"]

# Le jeu d'exemple est en Charente-Maritime. On ne crée le département que
# pour ce code : un autre code attend `charger_communes`.
REGION_EXEMPLE = ("75", "Nouvelle-Aquitaine")
DEPARTEMENTS_EXEMPLE = {"17": "Charente-Maritime"}

# Ponctuation fréquente hors Latin-1 / WinAnsi d'Helvetica.
REMPLACEMENTS = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2014": "-",
    "\u2013": "-",
    "\u2212": "-",
    "\u2015": "-",
    "\u23af": "-",
    "\u2026": "...",
    "\u0153": "oe",
    "\u0152": "OE",
    "\u202f": " ",
    "\u00a0": " ",
    "\u2022": "-",
    "\uf0d7": "-",
    "\uf0a8": "-",
    "\u20ac": "EUR",
    "\u00ad": "",
}

LARGEUR_LIGNE = 90
MARGE_BASSE = 48
HAUTEUR_LIGNE = 14


def extraire_rang(titre: str) -> int:
    """Extrait le rang numérique situé au début du titre d'une contribution.

    Exemple : `"7. Manuscrit, 6 lignes, 31 mots (homme)"` -> `7`.
    """
    return int(titre.split(".", maxsplit=1)[0].strip())


def code_departement(code_insee: str) -> str:
    if code_insee.startswith(("97", "98")) and len(code_insee) >= 3:
        return code_insee[:3]
    return code_insee[:2]


def assurer_communes(entrees: list[dict]) -> None:
    """Crée les communes du jeu d'exemple qui ne sont pas déjà en base.

    `charger_communes` reste la source du référentiel : une commune déjà
    chargée n'est pas réécrite.
    """
    villes = {entree["city"]["insee"]: entree["city"] for entree in entrees}
    if not villes:
        return
    departements = {code_departement(code) for code in villes}
    if not any(code in DEPARTEMENTS_EXEMPLE for code in departements):
        return
    Region.objects.get_or_create(
        code=REGION_EXEMPLE[0], defaults={"nom": REGION_EXEMPLE[1]}
    )
    for code in departements & set(DEPARTEMENTS_EXEMPLE):
        Departement.objects.get_or_create(
            code=code,
            defaults={"nom": DEPARTEMENTS_EXEMPLE[code], "region_id": REGION_EXEMPLE[0]},
        )
    connus = set(DEPARTEMENTS_EXEMPLE) & set(
        Departement.objects.filter(code__in=departements).values_list("code", flat=True)
    )
    for code, ville in villes.items():
        departement = code_departement(code)
        if departement not in connus or Commune.objects.filter(code=code).exists():
            continue
        habitants = ville.get("habitants")
        Commune.objects.create(
            code=code,
            type=Commune.Type.COMMUNE,
            nom=ville["commune"],
            departement_id=departement,
            population=habitants if type(habitants) is int and habitants >= 0 else None,
        )


def vers_winansi(texte: str) -> str:
    """Texte affichable par Helvetica en WinAnsi, sans ajouter de glyphes."""
    for source, cible in REMPLACEMENTS.items():
        texte = texte.replace(source, cible)
    gardes = []
    for caractere in texte:
        if caractere == "\n":
            gardes.append(caractere)
            continue
        code = ord(caractere)
        if 32 <= code <= 126 or 160 <= code <= 255:
            gardes.append(caractere)
        else:
            gardes.append("?")
    return "".join(gardes)


def couper_lignes(texte: str) -> list[str]:
    lignes = []
    for paragraphe in vers_winansi(texte).split("\n"):
        if not paragraphe:
            lignes.append("")
            continue
        reste = paragraphe
        while len(reste) > LARGEUR_LIGNE:
            coupe = reste.rfind(" ", 0, LARGEUR_LIGNE + 1)
            if coupe < 40:
                coupe = LARGEUR_LIGNE
            lignes.append(reste[:coupe].rstrip())
            reste = reste[coupe:].lstrip()
        lignes.append(reste)
    return lignes or [""]


def _chaine_pdf(texte: str) -> str:
    return (
        "("
        + texte.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        + ")"
    )


def pdf_du_texte(texte: str) -> bytes:
    """Un PDF d'une ou plusieurs pages, assez simple pour l'iframe locale."""
    pages: list[list[tuple[int, str]]] = []
    bloc: list[tuple[int, str]] = []
    y = 800
    for ligne in couper_lignes(texte):
        if y < MARGE_BASSE:
            pages.append(bloc)
            bloc = []
            y = 800
        bloc.append((y, ligne))
        y -= HAUTEUR_LIGNE
    pages.append(bloc or [(800, "")])

    objets: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
    }
    enfants = []
    numero = 4
    for bloc in pages:
        page_id, contenu_id = numero, numero + 1
        numero += 2
        morceaux = ["BT", "/F1 11 Tf"]
        for ordonnee, ligne in bloc:
            morceaux.append(f"1 0 0 1 50 {ordonnee} Tm {_chaine_pdf(ligne)} Tj")
        flux = "\n".join(morceaux + ["ET"]).encode("latin-1")
        objets[contenu_id] = (
            f"<< /Length {len(flux)} >>\nstream\n".encode("ascii")
            + flux
            + b"\nendstream"
        )
        objets[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {contenu_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode("ascii")
        enfants.append(f"{page_id} 0 R")
    objets[2] = (
        f"<< /Type /Pages /Kids [{' '.join(enfants)}] /Count {len(enfants)} >>"
    ).encode("ascii")

    sortie = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for identifiant in range(1, numero):
        offsets[identifiant] = len(sortie)
        sortie += f"{identifiant} 0 obj\n".encode("ascii")
        sortie += objets[identifiant] + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {numero}\n".encode("ascii")
    sortie += b"0000000000 65535 f \n"
    for identifiant in range(1, numero):
        sortie += f"{offsets[identifiant]:010d} 00000 n \n".encode("ascii")
    sortie += (
        f"trailer\n<< /Size {numero} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(sortie)


def document_d_entree(entree: dict) -> Document:
    nom_fichier = Path(entree["pdf_files"][0]).name
    document = noms.document(nom_fichier)
    if not document.categorie:
        document.categorie = Document.Categorie.CAHIER
    if not document.code_insee:
        document.code_insee = entree["city"]["insee"]
    if not document.code_postal:
        morceaux = nom_fichier.split("_")
        document.code_postal = morceaux[1] if len(morceaux) > 1 else ""
    return document


def deposer_extraits(run: Run) -> None:
    for contribution in run.contributions.all():
        if contribution.extrait:
            contribution.extrait.delete(save=False)
        contribution.extrait.save(
            f"{contribution.pk}.pdf",
            ContentFile(pdf_du_texte(contribution.texte)),
            save=True,
        )


def activer_si_seul(run: Run) -> None:
    """La page publique ne montre que le run actif. L'exemple le devient
    tant qu'aucune autre délimitation (la main, l'édition complète) ne l'est."""
    if run.actif:
        return
    if Run.objects.filter(genre=Run.Genre.DELIMITATION, actif=True).exists():
        return
    run.actif = True
    run.save(update_fields=["actif"])


class Command(BaseCommand):
    help = (
        "Charge les extraits choisis des transcriptions de Marie-Anne Chabin "
        "et les prépare pour la page d'accueil."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichier",
            type=Path,
            default=settings.BASE_DIR
            / "cahiers"
            / "data"
            / "cahiers_chabin_extraits.json",
            help=(
                "Chemin du fichier JSON des extraits Chabin "
                "(défaut : cahiers/data/cahiers_chabin_extraits.json)"
            ),
        )

    @transaction.atomic
    def handle(self, *args, fichier: Path, **options):
        if not fichier.is_file():
            raise CommandError(f"Fichier introuvable : {fichier}")

        entrees = json.loads(fichier.read_text(encoding="utf-8"))

        run, _ = Run.objects.update_or_create(
            genre=Run.Genre.DELIMITATION,
            libelle=LIBELLE,
            defaults={"auteur": AUTEUR},
        )

        assurer_communes(entrees)

        documents = [document_d_entree(entree) for entree in entrees]
        Document.objects.bulk_create(
            documents,
            update_conflicts=True,
            unique_fields=["fichier"],
            update_fields=CHAMPS_DOCUMENT,
        )

        noms_fichiers = [doc.fichier for doc in documents]
        ids_documents = dict(
            Document.objects.filter(fichier__in=noms_fichiers).values_list(
                "fichier", "id"
            )
        )

        contributions = []
        for entree in entrees:
            nom_fichier = Path(entree["pdf_files"][0]).name
            document_id = ids_documents[nom_fichier]
            for item in entree["contributions"]:
                contributions.append(
                    Contribution(
                        run=run,
                        document_id=document_id,
                        rang=extraire_rang(item["title"]),
                        texte=item["text"],
                        page_debut=0,
                        page_fin=0,
                    )
                )

        Contribution.objects.bulk_create(
            contributions,
            update_conflicts=True,
            unique_fields=["run", "document", "rang"],
            update_fields=CHAMPS_CONTRIBUTION,
        )
        deposer_extraits(run)
        activer_si_seul(run)

        self.stdout.write(
            f"{len(contributions)} contributions chargées dans "
            f"{len(documents)} documents, run « {run} »."
        )
