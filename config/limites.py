"""Limites anti-abus (essais de mot de passe, envois de commandes en rafale).
Les compteurs sont gardés dans le cache de Django pendant une durée donnée."""
import os

from django.core.cache import cache


def adresse_ip(request):
    # Derrière un hébergeur/proxy (Render, Nginx…), la vraie adresse est dans X-Forwarded-For
    if os.environ.get("DJANGO_DERRIERE_PROXY") == "1":
        transmise = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if transmise:
            return transmise.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "inconnue")


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
