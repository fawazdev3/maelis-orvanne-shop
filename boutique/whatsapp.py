"""Construction du message et du lien WhatsApp d'une commande."""
from urllib.parse import quote

from django.conf import settings


def _montant(n):
    return f"{n:,}".replace(",", " ") + " FCFA"


def _nom():
    from .models import ReglagesSite

    return ReglagesSite.charger().nom_boutique


def _livraison(commande):
    if commande.livraison_a_confirmer:
        return f"à confirmer pour {commande.ville}"
    return _montant(commande.frais_livraison) if commande.frais_livraison else "offerte"


def message_commande(commande):
    lignes = [
        f"Bonjour {_nom()}, je souhaite passer cette commande :",
        "",
        f"Commande n° {commande.numero}",
    ]
    for ligne in commande.lignes.all():
        lignes.append(f"• {ligne.nom_produit} × {ligne.quantite} = {_montant(ligne.sous_total)}")
    lignes += [
        "",
        f"Articles : {_montant(commande.montant_articles)}",
        f"Livraison : {_livraison(commande)}",
        f"Total : {_montant(commande.total)}" + (" + frais d'envoi" if commande.livraison_a_confirmer else ""),
        f"Paiement : {commande.get_mode_paiement_display()}",
        "",
        f"Nom : {commande.nom_client}",
        f"WhatsApp : {commande.telephone}",
        f"Ville : {commande.ville} ({commande.nom_pays})" + (f", {commande.lieu_livraison}" if commande.lieu_livraison else ""),
    ]
    if commande.note:
        lignes.append(f"Message : {commande.note}")
    lignes += ["", "Je vous envoie ma position juste après ce message."]
    return "\n".join(lignes)


def lien_whatsapp(commande):
    """Lien wa.me vers le numéro de la boutique, avec le message déjà rempli. None si le numéro n'est pas réglé."""
    from .models import ReglagesSite

    numero = ReglagesSite.charger().whatsapp_effectif
    if not numero:
        return None
    return f"https://wa.me/{numero}?text={quote(message_commande(commande))}"


# ---------------------------------------------------------------- Back-office : messages au client et au livreur

def _articles(commande):
    return [f"• {l.nom_produit} × {l.quantite}" for l in commande.lignes.all()]


def _paiement(commande):
    if commande.paiement_recu:
        return "déjà payée"
    if commande.livraison_a_confirmer:
        return f"{_montant(commande.montant_articles)} + frais d'envoi, à payer à la réception"
    if commande.mode_paiement == commande.ModePaiement.MOBILE_MONEY:
        return f"{_montant(commande.total)} à payer par Mobile Money à la réception"
    return f"{_montant(commande.total)} à payer en espèces à la réception"


def messages_client(commande):
    """Messages prêts à envoyer au client, un par étape. `suggere` met en avant l'étape logique suivante."""
    prenom = commande.nom_client
    boutique = _nom()
    etapes = [
        {
            "cle": "confirmer",
            "titre": "Confirmer la commande",
            "resume": "Récapitulatif, total et adresse",
            "icone": "bi-check2-circle",
            "pour": ["nouvelle"],
            "texte": "\n".join(
                [f"Bonjour {prenom}, ici {boutique}.", f"Nous avons bien reçu votre commande {commande.numero} :"]
                + _articles(commande)
                + [
                    "",
                    f"Livraison : {_livraison(commande)}."
                    if not commande.livraison_a_confirmer
                    else f"Les frais d'envoi vers {commande.ville} vous seront précisés.",
                    f"Total : {_paiement(commande)}.",
                    "",
                    "Tout est correct ? Quand souhaitez-vous être livré(e) ?"
                    + ("" if commande.lieu_livraison else " Envoyez-nous votre position WhatsApp pour la livraison."),
                ]
            ),
        },
        {
            "cle": "en_route",
            "titre": "Annoncer la livraison",
            "resume": "Commande en route, montant à préparer",
            "icone": "bi-truck",
            "pour": ["confirmee"],
            "texte": (
                f"Bonjour {prenom}, votre commande {commande.numero} est en route. "
                f"Nous arrivons bientôt à {commande.ville}. "
                + ("Elle est déjà payée. " if commande.paiement_recu else f"Montant : {_paiement(commande)}. ")
                + "À tout de suite !"
            ),
        },
        {
            "cle": "merci",
            "titre": "Remercier le client",
            "resume": "Message de remerciement après la livraison",
            "icone": "bi-heart",
            "pour": ["en_livraison", "livree"],
            "texte": (
                f"Merci {prenom} pour votre confiance ! Votre commande {commande.numero} a bien été livrée. "
                f"Écrivez-nous ici pour votre prochaine commande. {boutique}"
            ),
        },
    ]
    for e in etapes:
        e["lien"] = f"https://wa.me/{commande.telephone_whatsapp}?text={quote(e['texte'])}"
        e["suggere"] = commande.statut in e["pour"]
    return etapes


def fiche_livraison(commande):
    """Fiche à transférer à la personne qui livre (WhatsApp demande à qui l'envoyer)."""
    adresse = ", ".join(x for x in [commande.lieu_livraison, commande.ville, commande.nom_pays] if x)
    lignes = [
        f"LIVRAISON {commande.numero}",
        f"Client : {commande.nom_client}",
        f"Téléphone : {commande.telephone_affiche}",
        f"Adresse : {adresse}",
        "Position : demandée au client sur WhatsApp" if not commande.lieu_livraison
        else f"Carte : https://www.google.com/maps/search/?api=1&query={quote(adresse)}",
        "",
        "Articles :",
        *_articles(commande),
        "",
        f"À encaisser : {_paiement(commande)}",
    ]
    if commande.note:
        lignes.append(f"Message du client : {commande.note}")
    texte = "\n".join(lignes)
    return {"texte": texte, "lien": f"https://wa.me/?text={quote(texte)}"}
