"""Donne aux éditeurs et modérateurs le droit de voir et modifier les thématiques.

Django crée les permissions d'un modèle sans les attribuer à aucun groupe :
sans cette migration, `Editors` et `Moderators` ne voient pas le snippet
Thématique. Ni « ajouter » ni « supprimer » : la taxonomie est chargée par
`charger_thematiques`, et le formulaire Wagtail ne laisse modifier que la
description (`ThematiqueViewSet`).

Sur une base neuve, Django ne crée les permissions qu'après toutes les
migrations (signal `post_migrate`) : on les crée donc ici si elles manquent,
comme le fait `wagtailadmin/migrations/0001_create_admin_access_permissions.py`.

Pour un nouveau snippet, écrire une nouvelle migration sur ce modèle
(`makemigrations --empty cms`), sans modifier celle-ci.
"""

from django.db import migrations

GROUPES = ["Editors", "Moderators"]
ACTIONS = ["view", "change"]


def permissions_thematique(apps):
    """Renvoie les permissions accordées, créées si elles manquent."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    type_contenu, _ = ContentType.objects.get_or_create(
        app_label="cahiers", model="thematique"
    )
    return [
        Permission.objects.get_or_create(
            content_type=type_contenu,
            codename=f"{action}_thematique",
            defaults={"name": f"Can {action} thématique"},
        )[0]
        for action in ACTIONS
    ]


def accorder(apps, schema_editor):
    """Ajoute les permissions aux groupes éditoriaux."""
    Group = apps.get_model("auth", "Group")
    permissions = permissions_thematique(apps)
    for groupe in Group.objects.filter(name__in=GROUPES):
        groupe.permissions.add(*permissions)


def retirer(apps, schema_editor):
    """Retire ces permissions aux groupes, sans supprimer les permissions."""
    Group = apps.get_model("auth", "Group")
    permissions = permissions_thematique(apps)
    for groupe in Group.objects.filter(name__in=GROUPES):
        groupe.permissions.remove(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0003_homepage_hero_text"),
        ("cahiers", "0005_thematique"),
        # Crée les groupes Editors et Moderators.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(accorder, retirer)]
