from django.contrib import admin
from django.urls import path

admin.site.site_header = "Les cahiers pour décider et agir"
admin.site.site_title = "Cahiers"

urlpatterns = [
    path("admin/", admin.site.urls),
]
