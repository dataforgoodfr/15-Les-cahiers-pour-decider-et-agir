"""Vues d'administration Wagtail propres à la plateforme."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def peut_generer_lien(demandeur, cible):
    """Dit si `demandeur` peut générer le lien de réinitialisation de `cible`.

    Seul un superutilisateur le peut, et jamais pour son propre compte (on
    change son mot de passe depuis « Mon compte »).

    - Un développeur (`is_staff`) vise tout autre compte.
    - Un administrateur Wagtail (superutilisateur sans `is_staff`) ne vise que
      les éditeurs et modérateurs. Un compte `is_staff` lui donnerait l'admin
      Django ; un autre administrateur Wagtail, la main sur un pair. Les
      administrateurs Wagtail relèvent donc des développeurs.
    """
    if not demandeur.is_superuser or demandeur.pk == cible.pk:
        return False
    if demandeur.is_staff:
        return True
    return not (cible.is_staff or cible.is_superuser)


def lien_reinitialisation(request, pk):
    """Affiche un lien de réinitialisation à transmettre à la main.

    Le lien mène à la page de réinitialisation de Wagtail, sans passer par
    un courriel. `uidb64` ne fait qu'identifier le compte ; la sécurité tient
    au jeton, un HMAC-SHA256 signé avec `SECRET_KEY`. Il expire après
    `PASSWORD_RESET_TIMEOUT` et ne sert qu'une fois : il dépend du mot de
    passe et de la dernière connexion. Un refus lève `PermissionDenied`, que
    Wagtail convertit en redirection vers l'accueil de l'admin.
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    cible = get_object_or_404(get_user_model(), pk=pk)
    if not peut_generer_lien(request.user, cible):
        raise PermissionDenied

    chemin = reverse(
        "wagtailadmin_password_reset_confirm",
        args=[
            urlsafe_base64_encode(force_bytes(cible.pk)),
            default_token_generator.make_token(cible),
        ],
    )
    return TemplateResponse(
        request,
        "cms/lien_reinitialisation.html",
        {
            "page_title": "Lien de réinitialisation",
            "header_icon": "key",
            "cible": cible,
            "lien": request.build_absolute_uri(chemin),
            "validite_jours": settings.PASSWORD_RESET_TIMEOUT // 86_400,
        },
    )
