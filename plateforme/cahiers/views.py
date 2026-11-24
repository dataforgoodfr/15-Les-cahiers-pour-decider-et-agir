"""Les pages publiques : seulement des contributions montrables.

Le public ne voit que l'extrait d'une contribution, caviardé et relu
(`Contribution.extrait`), jamais le PDF du cahier (`Document.pdf`), qui
n'est pas anonymisé et n'a aucune adresse publique.
"""

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import Contribution, Thematique


def accueil(request):
    """Une contribution tirée au sort parmi les montrables (#30). « Afficher
    une autre contribution » écarte celle qu'on vient de voir."""
    montrables = Contribution.objects.montrables()
    total = montrables.count()
    precedente = request.GET.get("apres", "")
    if precedente.isdigit() and total > 1:
        montrables = montrables.exclude(pk=int(precedente))
    contribution = (
        montrables.select_related("document__commune__departement")
        .order_by("?")
        .first()
    )
    return render(
        request,
        "cahiers/accueil.html",
        {"contribution": contribution, "total": total},
    )


@xframe_options_sameorigin
def extrait(request, pk: int):
    """Le PDF caviardé d'une contribution montrable, affiché dans la page."""
    contribution = get_object_or_404(Contribution.objects.montrables(), pk=pk)
    return FileResponse(
        contribution.extrait.open("rb"),
        content_type="application/pdf",
        filename=f"contribution-{contribution.pk}.pdf",
    )


def apercu_thematiques(request):
    """Aperçu temporaire de la taxonomie des thématiques (LOCAL et STAGING).

    Permet à l'équipe projet de consulter facilement les thèmes, sous-thèmes,
    slugs et descriptions avant l'arrivée des pages Wagtail dédiées.
    Refuse l'accès en production.
    """
    if settings.ENV == "PROD":
        raise Http404("Cette page d'aperçu n'est pas disponible en production.")
    themes = Thematique.objects.avec_sous_thematiques()
    return render(
        request,
        "cahiers/thematiques_apercu.html",
        {"themes": themes},
    )
