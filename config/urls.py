from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Back-office sur mesure de la boutique
    path("gestion/", include("gestion.urls")),
    # Administration Django de secours (pour l'administrateur technique)
    path("admin-technique/", admin.site.urls),
    # Site public (catalogue, panier) : construit à l'étape suivante
    path("", include("boutique.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
