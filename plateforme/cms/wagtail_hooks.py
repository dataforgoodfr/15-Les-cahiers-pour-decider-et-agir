"""Intégration Wagtail des modèles métier de la plateforme.

Les modèles métier de `cahiers` (comme `Thematique`) restent découplés de
Wagtail : leur exposition dans le backoffice éditorial est centralisée ici.
"""

from django.db.models import F
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.panels import FieldPanel
from wagtail.admin.widgets.button import Button
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from cahiers.models import Thematique

from .views import lien_reinitialisation, peut_generer_lien


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


@hooks.register("register_admin_urls")
def urls_lien_reinitialisation():
    """Ajoute à l'admin Wagtail la page du lien de réinitialisation."""
    return [
        path(
            "utilisateurs/<int:pk>/lien-reinitialisation/",
            lien_reinitialisation,
            name="cms_lien_reinitialisation",
        ),
    ]


@hooks.register("register_user_listing_buttons")
def bouton_lien_reinitialisation(user, request_user):
    """Ajoute « Lien de réinitialisation » au menu de chaque compte.

    Sans serveur SMTP, c'est ainsi qu'une personne choisit son mot de passe :
    l'administrateur Wagtail génère le lien et le lui transmet.
    """
    if not peut_generer_lien(request_user, user):
        return []
    return [
        Button(
            "Lien de réinitialisation",
            reverse("cms_lien_reinitialisation", args=[user.pk]),
            icon_name="key",
        )
    ]
