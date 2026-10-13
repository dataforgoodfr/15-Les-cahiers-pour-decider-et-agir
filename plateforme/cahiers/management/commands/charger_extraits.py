"""Rattache aux contributions leur PDF caviardé et relu (#30).

Lit `selection/selection.csv` et `selection/pdf/` (sortie de `python -m
selection`) : pour chaque contribution tirée et exportée, le PDF réduit à ses
pages, données personnelles caviardées, relu à la main. C'est le seul fichier
que la plateforme montre au public.

Le PDF va à la contribution de même rang du run de délimitation à la main
(`charger_contributions`, à lancer avant), si elle est publiable et que ses
pages sont les mêmes ; sinon il est refusé. Les extraits des contributions qui
ne sont plus exportées sont retirés. La commande peut être relancée.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cahiers.management.commands.charger_contributions import LIBELLE
from cahiers.models import Contribution, Run


class Command(BaseCommand):
    help = "Rattache aux contributions leur PDF caviardé et relu."

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyse",
            dest="data",
            type=Path,
            default=settings.BASE_DIR.parent / "analyse" / "data",
            help="dossier des sorties d'analyse/ (défaut : ../analyse/data)",
        )

    @transaction.atomic
    def handle(self, *args, data: Path, **options):
        chemin = data / "selection" / "selection.csv"
        if not chemin.is_file():
            raise CommandError(f"pas de {chemin} : lancer python -m selection")
        run = Run.objects.filter(genre=Run.Genre.DELIMITATION, libelle=LIBELLE).first()
        if run is None:
            raise CommandError("pas de délimitation à la main : charger_contributions")
        with chemin.open(encoding="utf-8", newline="") as f:
            exportes = [x for x in csv.DictReader(f) if x["statut"] == "exporté"]

        gardes, refus = set(), []
        for x in exportes:
            contribution = (
                Contribution.objects.filter(
                    run=run, document__fichier=x["fichier"], rang=int(x["rang"])
                )
                .select_related("document")
                .first()
            )
            pages = (int(x["page_debut"]), int(x["page_fin"]))
            if contribution is None:
                refus.append(f"{x['fichier']} : contribution {x['rang']} absente")
                continue
            if not contribution.publiable:
                refus.append(f"{x['fichier']} : contribution {x['rang']} non publiable")
                continue
            if (contribution.page_debut, contribution.page_fin) != pages:
                refus.append(f"{x['fichier']} : pages différentes de la délimitation")
                continue
            if contribution.extrait:
                contribution.extrait.delete(save=False)
            with (data / "selection" / x["pdf"]).open("rb") as pdf:
                # un nom neutre : celui du fichier BnF n'a rien à faire en ligne
                contribution.extrait.save(f"{contribution.pk}.pdf", File(pdf))
            gardes.add(contribution.pk)

        retires = 0
        for contribution in run.contributions.exclude(extrait="").exclude(
            pk__in=gardes
        ):
            contribution.extrait.delete(save=True)
            retires += 1

        self.stdout.write(
            f"{len(gardes)} extraits rattachés, {retires} retirés, "
            f"{len(refus)} refusés."
        )
        for raison in refus:
            self.stdout.write(f"  refusé : {raison}")
