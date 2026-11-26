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

    Seul un superutilisateur le peut. Un administrateur Wagtail (sans
    `is_staff`) ne vise pas un compte `is_staff` : il prendrait sinon la main
    sur un compte développeur, et donc sur l'admin Django.
    """
    return demandeur.is_superuser and (demandeur.is_staff or not cible.is_staff)


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
