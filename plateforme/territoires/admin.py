from django.contrib import admin

from .models import Commune, Departement, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["code", "nom"]
    search_fields = ["code", "nom"]


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "region"]
    list_filter = ["region"]
    search_fields = ["code", "nom"]


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "type", "departement", "population", "nom_courant"]
    list_filter = ["type", "departement__region"]
    list_select_related = ["departement"]
    search_fields = ["code", "nom", "code_courant", "nom_courant"]
    autocomplete_fields = ["departement", "commune_parente"]
