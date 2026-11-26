from django.shortcuts import render

CHEMINS_LIBRES = ("/gestion/", "/admin-technique/", "/static/", "/media/")


class MaintenanceMiddleware:
    """Quand le mode maintenance est activé, les visiteurs voient une page d'attente.
    L'équipe connectée au back-office continue de voir le site normalement."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(CHEMINS_LIBRES) and not (request.user.is_authenticated and request.user.is_staff):
            from .models import ReglagesSite

            reglages = ReglagesSite.charger()
            if reglages.maintenance_active():
                from django.utils import timezone

                contexte = {"reglages": reglages, "fin_texte": reglages.fin_maintenance_texte()}
                reponse = render(request, "boutique/maintenance.html", contexte, status=503)
                if reglages.fin_maintenance:
                    secondes = int((reglages.fin_maintenance - timezone.now()).total_seconds())
                    reponse["Retry-After"] = str(max(secondes, 60))
                return reponse
        return self.get_response(request)
