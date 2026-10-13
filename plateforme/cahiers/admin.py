from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Contribution, Document, Page, Rattachement, Run, Transcription


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
