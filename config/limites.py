"""Limites anti-abus (essais de mot de passe, envois de commandes en rafale).
Les compteurs sont gardés dans le cache de Django pendant une durée donnée."""
from ipaddress import ip_address

from django.conf import settings
from django.core.cache import cache


def adresse_ip(request):
    distante = request.META.get("REMOTE_ADDR", "inconnue")
    try:
        adresse_distante = ip_address(distante)
    except ValueError:
        return distante

    proxies_fiables = getattr(settings, "TRUSTED_PROXIES", ())
    if not any(adresse_distante in proxy for proxy in proxies_fiables):
        return str(adresse_distante)

    transmises = request.META.get("HTTP_X_FORWARDED_FOR", "")
    for candidate in reversed(transmises.split(",")):
        try:
            adresse = ip_address(candidate.strip())
        except ValueError:
            return str(adresse_distante)
        if not any(adresse in proxy for proxy in proxies_fiables):
            return str(adresse)
    return str(adresse_distante)


def compte(cle):
    return cache.get(f"limite:{cle}", 0)


def ajouter(cle, duree):
    cle = f"limite:{cle}"
    try:
        cache.add(cle, 0, duree)
        return cache.incr(cle)
    except ValueError:
        cache.set(cle, 1, duree)
        return 1


def effacer(cle):
    cache.delete(f"limite:{cle}")
