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
    list_display = ["code_insee", "nom", "departement", "population"]
    list_filter = ["departement__region"]
    list_select_related = ["departement"]
    search_fields = ["code_insee", "nom"]
    autocomplete_fields = ["departement", "commune_parente"]

    def get_search_results(self, request, queryset, search_term):
        """Cherche aussi par code postal."""
        resultats, doublons = super().get_search_results(request, queryset, search_term)
        if search_term.isdigit() and len(search_term) == 5:
            resultats |= queryset.filter(codes_postaux__contains=[search_term])
        return resultats, doublons
