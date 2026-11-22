from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from cahiers import views as cahiers_views
from cms import urls as cms_urls

admin.site.site_header = "Les cahiers pour décider et agir"
admin.site.site_title = "Cahiers"

urlpatterns = [
    path("django-admin/", admin.site.urls),
]

# Aperçu provisoire des thématiques (retiré lors de l'arrivée des pages Wagtail).
if settings.ENV != "PROD":
    urlpatterns.append(
        path(
            "thematiques/",
            cahiers_views.apercu_thematiques,
            name="apercu_thematiques",
        )
    )

urlpatterns += [
    path("", include(cms_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
