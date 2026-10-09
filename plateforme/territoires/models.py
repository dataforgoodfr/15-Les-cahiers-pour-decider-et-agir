"""Le découpage administratif de geo.api.gouv.fr, auquel on rattache les cahiers."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

# Les cahiers dont la commune n'est pas identifiée, ou qui viennent de
# l'étranger, sont rattachés à cette commune.
CODE_INCONNU = "99999"


class Region(models.Model):
    code = models.CharField(max_length=3, unique=True)
    nom = models.CharField(max_length=100)

    class Meta:
        verbose_name = "région"
        ordering = ["code"]

    def __str__(self):
        return self.nom


class Departement(models.Model):
    code = models.CharField(max_length=3, unique=True)
    nom = models.CharField(max_length=100)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="departements"
    )

    class Meta:
        verbose_name = "département"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.nom}"


class Commune(models.Model):
    code_insee = models.CharField(max_length=5, unique=True)
    nom = models.CharField(max_length=100)
    departement = models.ForeignKey(
        Departement, on_delete=models.PROTECT, related_name="communes"
    )
    # Pour les arrondissements de Paris, Lyon et Marseille.
    commune_parente = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="arrondissements",
    )
    codes_postaux = ArrayField(models.CharField(max_length=5), default=list, blank=True)
    population = models.PositiveIntegerField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["code_insee"]

    def __str__(self):
        return f"{self.nom} ({self.code_insee})"
