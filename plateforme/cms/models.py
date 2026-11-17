from django.db import models
from wagtail.models import Page


class HomePage(Page):
    hero_text = models.CharField(
        max_length=255,
        help_text="Texte affiché dans la section hero de la page d'accueil",
        blank=True,
    )

    content_panels = Page.content_panels + ["hero_text"]


# Create your models here.
