"""Intégration Wagtail des modèles métier de la plateforme.

Les modèles métier de `cahiers` (comme `Thematique`) restent découplés de
Wagtail : leur exposition dans le backoffice éditorial est centralisée ici.
"""

from django.db.models import F
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from cahiers.models import Thematique


class ThematiqueViewSet(SnippetViewSet):
    """Expose `Thematique` dans le backoffice Wagtail pour les éditeurs.

    La structure de la taxonomie (`nom`, `parent`, `slug`, `ordre`) est figée
    et administrée côté Django Admin ou via la commande `charger_thematiques`.
    Dans Wagtail, ces champs sont affichés en lecture seule pour le contexte,
    et seule `description` est éditable (y compris côté serveur : les panneaux
    `read_only=True` sont exclus du formulaire généré par Wagtail).

    Pour accorder cet accès à un groupe d'éditeurs dans Wagtail, cocher
    uniquement les permissions « Peut voir thématique » et « Peut modifier
    thématique » (sans « Ajouter » ni « Supprimer »).
    """

    model = Thematique
    icon = "tag"
    menu_label = "Thématiques"
    menu_name = "thematiques"
    add_to_admin_menu = True
    list_display = ["nom", "parent", "ordre", "slug"]
    list_filter = ["parent"]
    search_fields = ["nom", "slug", "description"]

    panels = [
        FieldPanel("nom", read_only=True),
        FieldPanel("parent", read_only=True),
        FieldPanel("slug", read_only=True),
        FieldPanel("ordre", read_only=True),
        FieldPanel("description"),
    ]

    def get_queryset(self, request):
        """Trie les thèmes principaux puis leurs sous-thèmes dans leur ordre."""
        return (
            Thematique.objects.select_related("parent")
            .order_by(F("parent__ordre").asc(nulls_first=True), "ordre", "nom")
        )


register_snippet(ThematiqueViewSet)
