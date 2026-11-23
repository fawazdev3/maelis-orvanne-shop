from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path

# L'administration technique utilise la page de connexion du back-office (limitée à 5 essais)
admin.site.login = login_required(admin.site.login, login_url="gestion:connexion")

urlpatterns = [
    # Back-office sur mesure de la boutique
    path("gestion/", include("gestion.urls")),
    # Administration Django de secours (pour l'administrateur technique)
    path("admin-technique/", admin.site.urls),
    # Site public (catalogue, panier, commande)
    path("", include("boutique.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
