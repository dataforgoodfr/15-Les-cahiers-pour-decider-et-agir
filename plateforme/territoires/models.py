"""Le découpage administratif au 1er janvier 2019, auquel on rattache les cahiers.

Un code INSEE est une clé datée. Ceux des cahiers ont été attribués au dépôt,
en février-avril 2019, et des communes ont fusionné depuis : le référentiel est
donc celui de 2019, et le découpage actuel n'y est qu'une annotation.
"""

from django.db import models


class Region(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    nom = models.CharField(max_length=100)

    class Meta:
        verbose_name = "région"
        ordering = ["code"]

    def __str__(self):
        return self.nom


class Departement(models.Model):
    code = models.CharField(max_length=3, primary_key=True)
    nom = models.CharField(max_length=100)
    # Vide pour les collectivités d'outre-mer, qui n'ont pas de région.
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="departements",
    )

    class Meta:
        verbose_name = "département"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.nom}"


class Commune(models.Model):
    class Type(models.TextChoices):
        COMMUNE = "COM", "commune"
        DELEGUEE = "COMD", "commune déléguée"
        ASSOCIEE = "COMA", "commune associée"
        ARRONDISSEMENT = "ARM", "arrondissement municipal"

    # Code INSEE de 2019, 2A et 2B pour la Corse. Il ne change jamais.
    code = models.CharField(max_length=5, primary_key=True)
    type = models.CharField(max_length=4, choices=Type)
    nom = models.CharField(max_length=100)
    departement = models.ForeignKey(
        Departement, on_delete=models.PROTECT, related_name="communes"
    )
    # Commune absorbante d'une commune déléguée ou associée, ou commune d'un
    # arrondissement. Deux cahiers ont été déposés sous le code d'une commune
    # déjà absorbée en 2019.
    commune_parente = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rattachees",
    )
    # Population municipale 2017, dans les limites de 2019. Celle d'une entité
    # rattachée est déjà comprise dans celle de sa parente : ne pas les sommer.
    population = models.PositiveIntegerField(null=True, blank=True)
    # Centre de la commune dans le découpage actuel : vide pour les communes
    # disparues depuis 2019, plutôt que le centre de celle qui les a absorbées.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    # Ce que la commune est devenue au découpage actuel. Code vide : la chaîne
    # des mouvements ne mène à aucune commune actuelle.
    code_courant = models.CharField(max_length=5, blank=True)
    nom_courant = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.nom} ({self.code})"
