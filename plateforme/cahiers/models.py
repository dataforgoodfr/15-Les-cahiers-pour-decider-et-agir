"""Les documents du versement de la BnF, leurs pages, et les contributions.

Le document et ses pages sont la provenance : on ne les réécrit jamais. Ce
qu'on en lit (un découpage en contributions, une transcription, un repérage
des données personnelles) est une couche, rattachée à un run, et plusieurs
couches du même genre coexistent pour être comparées.

Une contribution est délimitée sur l'image, en points PDF, comme dans l'outil
d'annotation : c'est ce qui vaut aussi pour les pages manuscrites, que rien
n'a encore lues.
"""

from django.db import models
from django.db.models import F, Q

from territoires.models import Commune


class Document(models.Model):
    """Un fichier PDF du versement : cahier citoyen, courrier ou compte rendu."""

    class Categorie(models.TextChoices):
        CAHIER = "CC", "cahier citoyen"
        COURRIER = "CO", "courrier"
        REUNION = "CR", "compte rendu de réunion"
        REUNION_COURRIEL = "IL", "compte rendu de réunion par courriel"

    # Annotation de l'opérateur de numérisation, fiable au niveau du document
    # mais qui ne compte pas les pages. Tous les cahiers citoyens sont MD.
    class Mode(models.TextChoices):
        DACTYLOGRAPHIE = "D", "dactylographié"
        MANUSCRIT = "M", "manuscrit"
        MIXTE = "MD", "mixte"

    # `CC_01000_190304_01053_MD_15462.pdf` : la clé partout dans `analyse/`.
    fichier = models.CharField(max_length=100, unique=True)
    categorie = models.CharField(max_length=2, choices=Categorie)
    mode = models.CharField(max_length=2, choices=Mode, blank=True)
    code_postal = models.CharField(max_length=5, blank=True)
    date_depot = models.DateField(null=True, blank=True)
    numero = models.PositiveIntegerField(null=True, blank=True)
    # Code INSEE tel qu'écrit dans le nom du fichier, et la commune de 2019
    # qu'il désigne. Vide pour les courriers et les cahiers sans commune.
    code_insee = models.CharField(max_length=6, blank=True)
    commune = models.ForeignKey(
        Commune,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documents",
    )
    nombre_pages = models.PositiveIntegerField(null=True, blank=True)
    # Sur Cellar en production, bucket privé : les cahiers ne sont pas anonymisés.
    pdf = models.FileField(upload_to="documents/", blank=True)

    class Meta:
        ordering = ["fichier"]

    def __str__(self):
        return self.fichier


class Page(models.Model):
    class Type(models.TextChoices):
        VIERGE = "vierge", "vierge"
        DACTYLOGRAPHIEE = "dactylographiee", "dactylographiée"
        MIXTE = "mixte", "mixte"
        MANUSCRITE = "manuscrite", "manuscrite"

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="pages"
    )
    numero = models.PositiveIntegerField()  # à partir de 1
    type = models.CharField(max_length=15, choices=Type, blank=True)
    # Quart de tour à appliquer pour lire la page droite.
    rotation = models.PositiveSmallIntegerField(
        choices=[(0, "0°"), (90, "90°"), (180, "180°"), (270, "270°")], default=0
    )
    # Page ajoutée à la numérisation (mire, intercalaire), qui n'est pas du cahier.
    service = models.BooleanField(default=False)
    # Page d'ouverture imprimée (couverture de l'association des maires…), qui
    # n'est pas une contribution.
    ouverture = models.BooleanField(default=False)
    # Couche texte du PDF : du bruit sur les pages manuscrites.
    texte = models.TextField(blank=True)

    class Meta:
        ordering = ["document", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "numero"], name="page_unique_par_document"
            )
        ]

    def __str__(self):
        return f"{self.document} p. {self.numero}"


class Run(models.Model):
    """Une couche posée sur le corpus : qui l'a produite, comment, quand.

    Un seul run actif par genre : c'est celui que la plateforme sert. Les
    autres restent en base, lisibles et comparables.
    """

    class Genre(models.TextChoices):
        DELIMITATION = "delimitation", "délimitation des contributions"
        TRANSCRIPTION = "transcription", "transcription"
        ANONYMISATION = "anonymisation", "anonymisation"

    genre = models.CharField(max_length=20, choices=Genre)
    libelle = models.CharField(max_length=200)
    auteur = models.CharField(max_length=100)
    # Modèle et paramètres tels qu'appliqués, s'il y en a : une délimitation
    # faite à la main n'en a pas.
    modele = models.CharField(max_length=200, blank=True)
    parametres = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    cree = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=False)

    class Meta:
        ordering = ["-cree"]
        constraints = [
            models.UniqueConstraint(
                fields=["genre"], condition=Q(actif=True), name="un_run_actif_par_genre"
            )
        ]

    def __str__(self):
        return self.libelle


class Contribution(models.Model):
    """Ce qu'a écrit une personne, délimité dans un document.

    Elle commence à une hauteur d'une page et finit à une hauteur d'une autre,
    en points PDF dans le repère de la page non tournée. Une hauteur vide veut
    dire le haut de la page pour le début, le bas pour la fin.
    """

    run = models.ForeignKey(Run, on_delete=models.PROTECT, related_name="contributions")
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="contributions"
    )
    rang = models.PositiveIntegerField()  # dans le document, à partir de 1
    page_debut = models.PositiveIntegerField()
    y_debut = models.FloatField(null=True, blank=True)
    page_fin = models.PositiveIntegerField()
    y_fin = models.FloatField(null=True, blank=True)
    # Ce qui a délimité la contribution : une note de l'outil d'annotation,
    # une règle de découpage…
    origine = models.CharField(max_length=50, blank=True)
    # Le texte, quand une transcription l'a lu. Vide pour le manuscrit non lu.
    texte = models.TextField(blank=True)

    class Meta:
        ordering = ["document", "rang"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "document", "rang"], name="rang_unique_par_run"
            ),
            models.CheckConstraint(
                condition=Q(page_fin__gte=F("page_debut")),
                name="fin_apres_debut",
            ),
        ]

    def __str__(self):
        return f"{self.document} n° {self.rang}"

    @property
    def pages(self):
        return self.document.pages.filter(
            numero__gte=self.page_debut, numero__lte=self.page_fin
        )
