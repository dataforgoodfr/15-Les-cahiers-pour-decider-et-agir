"""Crée ou met à jour de façon idempotente les comptes Django (12-Factor).

- Superutilisateur : ``DJANGO_SUPERUSER_USERNAME`` / ``DJANGO_SUPERUSER_EMAIL``
  / ``DJANGO_SUPERUSER_PASSWORD`` (les mêmes variables que
  ``createsuperuser --noinput``).
- Utilisateurs standards (optionnel) : ``DJANGO_USERS``, liste JSON
  ``[{"username": "...", "email": "...", "staff": true, "password": "..."}]``.

Relançable à chaque déploiement (idempotent). Le mot de passe n'est posé qu'à
la création, sauf si ``DJANGO_FORCE_SUPERUSER_PASSWORD=1`` (rotation).
"""

import json
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Synchronise superusers et users Django depuis l'environnement."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if not username:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME absent : rien à faire.")
            return

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        force = os.environ.get("DJANGO_FORCE_SUPERUSER_PASSWORD") == "1"

        user, created = User.objects.get_or_create(username=username)
        if created and not password:
            raise CommandError(
                "DJANGO_SUPERUSER_PASSWORD manque pour créer le superutilisateur."
            )
        user.is_staff = True
        user.is_superuser = True
        if email := os.environ.get("DJANGO_SUPERUSER_EMAIL"):
            user.email = email
        if password and (created or force):
            user.set_password(password)
        user.save()
        self.stdout.write(
            f"Superutilisateur {'créé' if created else 'mis à jour'} : {username}"
        )

        for spec in json.loads(os.environ.get("DJANGO_USERS", "[]")):
            u, c = User.objects.get_or_create(username=spec["username"])
            u.is_staff = bool(spec.get("staff", False))
            u.is_superuser = bool(spec.get("superuser", False))
            if spec.get("email"):
                u.email = spec["email"]
            if spec.get("password") and (c or force):
                u.set_password(spec["password"])
            u.save()
        self.stdout.write("Utilisateurs synchronisés.")
