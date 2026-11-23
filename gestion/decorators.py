from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def gestionnaire_requis(vue):
    """Réserve une page aux comptes « membres du personnel » (is_staff) actifs."""

    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return vue(request, *args, **kwargs)

    return enveloppe


def acces_requis(section):
    """Réserve une page aux rôles qui ont accès à cette section (voir gestion/roles.py)."""

    def decorateur(vue):
        @wraps(vue)
        @gestionnaire_requis
        def enveloppe(request, *args, **kwargs):
            from .roles import peut

            if not peut(request.user, section):
                messages.error(request, "Votre rôle ne donne pas accès à cette page.")
                return redirect("gestion:tableau_de_bord")
            return vue(request, *args, **kwargs)

        return enveloppe

    return decorateur
