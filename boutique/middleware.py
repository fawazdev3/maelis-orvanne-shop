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
            if reglages.maintenance:
                return render(request, "boutique/maintenance.html", {"reglages": reglages}, status=503)
        return self.get_response(request)
