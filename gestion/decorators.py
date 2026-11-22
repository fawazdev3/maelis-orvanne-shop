from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def gestionnaire_requis(vue):
    """Réserve une page aux comptes « membres du personnel » (is_staff)."""

    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return vue(request, *args, **kwargs)

    return enveloppe
