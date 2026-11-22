from django.shortcuts import render


def accueil(request):
    """Page d'accueil provisoire : le catalogue et le panier arrivent à l'étape suivante."""
    return render(request, "boutique/accueil_provisoire.html")
