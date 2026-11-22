from django.contrib import admin
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Contribution,
    Document,
    Page,
    Rattachement,
    Run,
    Thematique,
    Transcription,
)


class RattachementInline(admin.TabularInline):
    model = Rattachement
    extra = 0
    autocomplete_fields = ["commune"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["fichier", "categorie", "commune", "date_depot", "nombre_pages"]
    list_filter = ["categorie", "mode", "commune__departement__region"]
    list_select_related = ["commune"]
    search_fields = ["fichier", "commune__nom", "code_insee"]
    autocomplete_fields = ["commune"]
    readonly_fields = ["voir_pages"]
    inlines = [RattachementInline]

    @admin.display(description="pages")
    def voir_pages(self, document):
        url = reverse("admin:cahiers_page_changelist")
        return format_html(
            '<a href="{}?document__id__exact={}">{} pages</a>',
            url,
            document.pk,
            document.pages.count(),
        )


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["document", "numero", "type", "rotation", "ouverture", "service"]
    list_filter = ["type", "ouverture", "service"]
    list_select_related = ["document"]
    search_fields = ["document__fichier"]
    raw_id_fields = ["document"]


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ["libelle", "genre", "auteur", "cree", "actif"]
    list_filter = ["genre", "actif"]


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ["page", "run", "qualite"]
    list_filter = ["run"]
    list_select_related = ["page__document", "run"]
    search_fields = ["page__document__fichier"]
    raw_id_fields = ["page"]


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "rang",
        "page_debut",
        "page_fin",
        "run",
        "origine",
        "publiable",
    ]
    list_filter = ["run", "publiable", "document__categorie"]
    list_select_related = ["document", "run"]
    search_fields = ["document__fichier"]
    raw_id_fields = ["document"]


class NiveauThematiqueFilter(admin.SimpleListFilter):
    """Filtre distinguant thèmes principaux (niveau 1) et sous-thèmes (niveau 2)."""

    title = "niveau"
    parameter_name = "niveau"

    def lookups(self, request, model_admin):
        return [
            ("theme", "Thèmes principaux"),
            ("sous_theme", "Sous-thèmes"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "theme":
            return queryset.filter(parent__isnull=True)
        if self.value() == "sous_theme":
            return queryset.filter(parent__isnull=False)
        return queryset


class ParentThematiqueFilter(admin.SimpleListFilter):
    """Filtre par thème principal (affiche uniquement les thèmes de niveau 1)."""

    title = "thème parent"
    parameter_name = "parent"

    def lookups(self, request, model_admin):
        return [
            (str(theme.pk), theme.nom)
            for theme in Thematique.objects.themes()
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(parent_id=self.value())
        return queryset


@admin.register(Thematique)
class ThematiqueAdmin(admin.ModelAdmin):
    list_display = ["nom", "slug", "parent", "ordre", "a_description"]
    list_filter = [NiveauThematiqueFilter, ParentThematiqueFilter]
    list_select_related = ["parent"]
    search_fields = ["nom", "slug", "description"]

    def get_queryset(self, request):
        """Trie les thèmes principaux en tête, puis leurs sous-thèmes par ordre."""
        return (
            super()
            .get_queryset(request)
            .select_related("parent")
            .order_by(F("parent__ordre").asc(nulls_first=True), "ordre", "nom")
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limite le choix du parent aux seuls thèmes principaux (2 niveaux max)."""
        if db_field.name == "parent":
            qs = Thematique.objects.themes()
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                qs = qs.exclude(pk=object_id)
            kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(boolean=True, description="description")
    def a_description(self, obj: Thematique) -> bool:
        return bool(obj.description.strip())
