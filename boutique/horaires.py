"""Horaires d'ouverture : la boutique est-elle ouverte maintenant, et quand rouvre-t-elle ?"""
from datetime import datetime, timedelta

from django.utils import timezone

from .models import HoraireJour, ReglagesSite, heure_fr

NOMS_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def horaires_semaine():
    """Les 7 jours, dans l'ordre, créés au besoin."""
    existants = {h.jour: h for h in HoraireJour.objects.all()}
    jours = []
    for num, _ in HoraireJour.JOURS:
        if num not in existants:
            existants[num] = HoraireJour.objects.create(jour=num, ouvert=num != 6)
        jours.append(existants[num])
    return jours


def etat_boutique(maintenant=None, reglages=None):
    """Renvoie None si les horaires ne sont pas appliqués, sinon un dictionnaire :
    ouvert, texte (phrase à afficher), commandes_possibles, semaine."""
    reglages = reglages or ReglagesSite.charger()
    if not reglages.horaires_actifs:
        return None
    maintenant = timezone.localtime(maintenant or timezone.now())
    semaine = horaires_semaine()
    aujourdhui = semaine[maintenant.weekday()]
    heure = maintenant.time()

    if aujourdhui.ouvert and aujourdhui.ouverture <= heure < aujourdhui.fermeture:
        fermeture = maintenant.replace(
            hour=aujourdhui.fermeture.hour, minute=aujourdhui.fermeture.minute, second=0, microsecond=0
        )
        return {
            "ouvert": True,
            "fermeture": heure_fr(aujourdhui.fermeture),
            "cible": fermeture,
            "bientot": (fermeture - maintenant) <= timedelta(hours=1),
            "texte": f"Ouvert aujourd'hui jusqu'à {heure_fr(aujourdhui.fermeture)}",
            "commandes_possibles": True,
            "semaine": semaine,
            "aujourdhui": aujourdhui.jour,
        }

    # Prochaine ouverture : plus tard aujourd'hui, ou dans les 7 jours suivants
    prochaine = None
    for decalage in range(0, 8):
        jour = semaine[(maintenant.weekday() + decalage) % 7]
        if not jour.ouvert or (decalage == 0 and heure >= jour.ouverture):
            continue
        prochaine = (decalage, jour)
        break

    cible = None
    if prochaine is None:
        quand = "prochainement"
    else:
        decalage, jour = prochaine
        h = heure_fr(jour.ouverture)
        date_ouverture = maintenant.date() + timedelta(days=decalage)
        cible = timezone.make_aware(datetime.combine(date_ouverture, jour.ouverture))
        if decalage == 0:
            quand = f"aujourd'hui à {h}"
        elif decalage == 1:
            quand = f"demain à {h}"
        else:
            quand = f"{NOMS_JOURS[jour.jour]} à {h}"

    return {
        "ouvert": False,
        "texte": f"La boutique est fermée pour le moment. Réouverture {quand}.",
        "quand": quand,
        "cible": cible,
        "bientot": False,
        "commandes_possibles": reglages.commandes_hors_horaires,
        "semaine": semaine,
        "aujourdhui": maintenant.weekday(),
    }


def livraison_gratuite_texte(pays_codes):
    """« partout au Togo » si toutes les villes du pays sont livrées gratuitement, sinon None."""
    from .models import TarifLivraison
    from .pays import PAYS

    gratuits = []
    for code in pays_codes:
        tarifs = list(TarifLivraison.objects.filter(pays=code).values_list("ville_normalisee", "frais"))
        if tarifs and any(v == "" for v, _ in tarifs) and all(f == 0 for _, f in tarifs):
            gratuits.append(f"au {PAYS[code]['nom']}" if code in PAYS else code)
    if not gratuits:
        return None
    if len(gratuits) == 1:
        return f"partout {gratuits[0]}"
    return "partout " + ", ".join(gratuits[:-1]) + " et " + gratuits[-1]
