# Maélis Orvanne Shop

Boutique en ligne avec commande par WhatsApp et paiement à la livraison, pensée pour le Togo et la sous-région (Bénin, Ghana).
Le client choisit ses produits et valide sa commande en trois étapes. La commande est enregistrée dans le back-office, puis WhatsApp s'ouvre avec le message déjà rédigé.

**Technologies :** Django 5, Bootstrap 5, JavaScript sans framework. Base SQLite en développement, PostgreSQL en production.

---

## Fonctionnalités

### Site public
- **Accueil** : produits mis en avant, promotions et catégories.
- **Catalogue** : filtre par catégorie, recherche et tri (prix, promotions). Les produits épuisés restent visibles, sans pouvoir être ajoutés au panier.
- **Fiche produit** : photo, prix barré en promotion, choix de la quantité, boutons « Ajouter au panier » et « Commander maintenant », produits similaires.
- **Commande en trois étapes** :
  1. **Panier** : quantités modifiables et total calculé automatiquement. Le panier est gardé dans le navigateur.
  2. **Livraison** : pays, ville choisie dans une liste (ou « Autre ville »), nom et numéro WhatsApp. L'indicatif (+228, +229, +233) suit le pays. Le numéro est vérifié selon les règles du pays (Togo 8 chiffres, Bénin 10 chiffres commençant par 01, Ghana 0 + 9 chiffres) et enregistré au format international.
  3. **Confirmation** : récapitulatif, frais de livraison selon la ville, choix du paiement (espèces ou Mobile Money à la réception) et message facultatif.
- **Envoi WhatsApp** : après validation, WhatsApp s'ouvre vers le numéro de la boutique avec la commande complète. Le client envoie ensuite sa position.
- **Aucun paiement en ligne** : tout se règle à la livraison.

### Back-office (`/gestion/`)
- **Tableau de bord** : nouvelles commandes, montant encaissé, montant restant à encaisser, ventes des 30 derniers jours et ruptures de stock.
- **Commandes** :
  - liste filtrable et recherche (numéro, nom, téléphone, ville) ;
  - fiche détaillée avec statut (nouvelle, confirmée, en livraison, livrée, annulée), paiement reçu et note interne ;
  - frais de livraison modifiables, avec recalcul du total.
- **WhatsApp en un clic** : messages déjà rédigés pour le client (confirmer la commande, annoncer la livraison, remercier) et fiche de livraison à transmettre à la personne qui livre (adresse, carte, montant à encaisser).
- **Produits et catégories** : photo, description, prix normal, prix promotionnel (remise calculée automatiquement), prix d'achat (jamais visible des clients), stock, visibilité et mise en avant.
- **Stock** : chaque arrivage enregistre la quantité et le prix d'achat. Il met le stock à jour et crée la dépense correspondante. Le stock baisse quand une commande passe « Livrée », et remonte si elle est annulée. À 0, le produit s'affiche « épuisé ».
- **Dépenses** : par mois et par catégorie (publicité Facebook, transport et envoi de colis, emballage et divers, catégories personnalisées).
- **Statistiques** : ventes et bénéfice du jour et du mois, résultat détaillé par jour, mois ou année. Formule : ventes − coût d'achat des articles vendus + frais de livraison − dépenses. S'y ajoutent les produits les plus vendus et un export Excel des ventes et des dépenses.
- **Tarifs de livraison** : frais par ville et par pays. Un tarif à 0 signifie « gratuite » (c'est le cas partout au Togo, et le site l'annonce) ; un tarif vide signifie « à confirmer », et le montant se règle ensuite dans la commande.
- **Équipe et rôles** :
  - comptes à créer, modifier, désactiver ou supprimer ;
  - rôles personnalisables, avec les pages autorisées pour chacun.
  
  Le rôle **Administrateur** a accès à tout. Le rôle **Comptabilité** est fourni par défaut.
- **Réglages du site** :
  - nom, phrase d'accroche, numéro WhatsApp, pays livrés, réseaux sociaux et Pixel Facebook ;
  - horaires d'ouverture jour par jour, avec un bandeau toujours visible en haut du site : « Ouvert », compte à rebours jusqu'à la fermeture, alerte « Bientôt la fermeture » la dernière heure, puis « Boutique fermée » avec le décompte jusqu'à la réouverture. En dehors des horaires, les commandes attendent l'ouverture (ou restent possibles, au choix) ;
  - pause des commandes ;
  - mode maintenance avec heure de fin facultative : la page d'attente annonce le retour du site (« Demain à 14h », compte à rebours) et le site se rouvre tout seul à l'heure choisie ;
  - sauvegarde des données ;
  - retrait des données d'exemple.
- **Thèmes clair et sombre.**

---

## Installation (Windows)

Prérequis : Python 3.10 ou plus récent.

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.exemple .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Site public : http://127.0.0.1:8000/
- Back-office : http://127.0.0.1:8000/gestion/

Le compte créé avec `createsuperuser` est administrateur.

Les mêmes opérations existent en double-clic : `installer.bat`, `creer_compte.bat`, `lancer.bat`, `tests.bat`.

**Données d'exemple** (facultatif) : `python manage.py donnees_exemple` crée une catégorie, trois produits et une commande de test. On les retire ensuite depuis **Réglages du site** → Maintenance.

**Tests :** `python manage.py test`

**Après une mise à jour du code :** `python manage.py migrate`, puis relancer le serveur.

---

## Configuration

### Fichier `.env`
Copié depuis `.env.exemple`. Il ne doit jamais être partagé ni envoyé sur GitHub : il est exclu par `.gitignore`.

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | Clé secrète unique et longue. Obligatoire en production. |
| `DJANGO_DEBUG` | `1` en développement, `0` en production |
| `DJANGO_ALLOWED_HOSTS` | Domaines autorisés, ex. `maelisorvanne.com,www.maelisorvanne.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Ex. `https://maelisorvanne.com,https://www.maelisorvanne.com` |
| `DJANGO_DERRIERE_PROXY` | `1` si l'hébergeur passe par un proxy HTTPS |
| `DJANGO_TRUSTED_PROXY_IPS` | IP/CIDR des reverse proxies de confiance, séparés par des virgules |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | `1` uniquement si tous les sous-domaines sont exclusivement en HTTPS |
| `DJANGO_MEDIA_ROOT` | Répertoire d'un volume persistant pour les photos (obligatoire en production) |
| `DJANGO_CACHE_URL` | URL Redis du cache partagé (obligatoire en production) |
| `BOUTIQUE_WHATSAPP`, `BOUTIQUE_PAYS` | Valeurs par défaut. Le back-office (Réglages du site) les remplace. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Base PostgreSQL. SQLite est réservé au développement. |

En production, configurez le reverse proxy pour transmettre le protocole HTTPS et une adresse client fiable, et pour écraser ou compléter `X-Forwarded-For` avec l'adresse réelle du client. `DJANGO_TRUSTED_PROXY_IPS` doit contenir l'adresse (ou le réseau) du proxy qui se connecte à Django. Les paramètres de production refusent de démarrer si PostgreSQL, Redis ou un chemin de médias persistant ne sont pas configurés. Le fichier `requirements.txt` contient les pilotes nécessaires.

### Réglages modifiables sans toucher au code
Depuis le back-office :
- **Réglages du site** : numéro WhatsApp, pays livrés, nom, accroche, réseaux sociaux, Pixel Facebook, horaires d'ouverture, pause des commandes, maintenance ;
- **Livraison** : tarifs par ville ;
- **Équipe et rôles** : comptes et droits.

Les listes de villes et les règles des numéros de téléphone se trouvent dans `boutique/pays.py`.

---

## Adresses

| Adresse | Page |
|---|---|
| `/` | Accueil |
| `/boutique/`, `/boutique/<catégorie>/` | Catalogue |
| `/produit/<nom>/` | Fiche produit |
| `/panier/` | Commande en trois étapes |
| `/commande/<jeton>/merci/` | Confirmation (lien secret propre à chaque commande) |
| `/gestion/` | Back-office |
| `/admin-technique/` | Administration Django de secours |

---

## Organisation du projet

```
maelis_orvanne/
├── config/                 Réglages Django, adresses, limites anti-abus
├── boutique/               Données et site public
│   ├── models.py           Produits, catégories, commandes, stock, dépenses, tarifs, réglages
│   ├── views.py            Pages publiques, commande, API du panier
│   ├── forms.py            Formulaire de commande
│   ├── pays.py             Pays livrés, villes, règles des numéros
│   ├── whatsapp.py         Messages WhatsApp (commande, client, livraison)
│   └── middleware.py       Mode maintenance
├── gestion/                Back-office
│   ├── views.py            Tableau de bord, produits, commandes, livraison, équipe
│   ├── views_finances.py   Stock, dépenses, statistiques, export
│   ├── views_reglages.py   Réglages du site, sauvegarde
│   └── roles.py            Rôles et accès par page
├── templates/              Pages HTML (boutique/ et gestion/)
├── static/                 CSS, JavaScript, favicon
└── media/                  Photos des produits (non versionné)
```

### Points techniques
- **Prix :** en FCFA, nombres entiers. Le serveur recalcule toujours les prix à partir de la base, jamais à partir du navigateur.
- **Lignes de commande :** chacune garde une copie du nom, du prix de vente et du prix d'achat au moment de l'achat, pour que l'historique et les statistiques restent justes.
- **Numéros de commande :** au format `MO-AAAAMMJJ-001`.
- **Ventes :** une vente compte dans les statistiques le jour où la commande est marquée « Livrée ».
- **Achats de marchandise :** ils ne sont pas retirés du bénéfice. Seul le coût d'achat des articles réellement vendus l'est.

---

## Sécurité

- **Connexion :** blocage de 15 minutes après 5 essais ratés. L'administration technique passe par la même page de connexion. Les mots de passe trop simples sont refusés.
- **Commandes :** 5 commandes au maximum par adresse IP en 10 minutes, plus un champ piège contre les robots.
- **Accès :** chaque page du back-office vérifie le rôle de l'utilisateur.
- **Protections Django :** CSRF, échappement des textes (XSS) et interdiction d'affichage dans un cadre (clickjacking).
- **Photos :** contenu vérifié (JPG, PNG ou WebP, 5 Mo maximum).
- **Export Excel :** les formules glissées dans les données clients sont neutralisées.
- **En production (`DJANGO_DEBUG=0`) :** HTTPS obligatoire, cookies sécurisés et HSTS sur le domaine (30 jours par défaut, sans sous-domaines). Le site refuse de démarrer sans une clé secrète de production valide.

Vérification avant la mise en ligne : `python manage.py check --deploy`
`security.W005` rappelle que les sous-domaines ne sont pas inclus par défaut. Définissez `DJANGO_HSTS_INCLUDE_SUBDOMAINS=1` uniquement si chacun doit exclusivement utiliser HTTPS. `security.W021` concerne l'option HSTS preload, volontairement désactivée ; ne l'activez qu'après avoir confirmé que tous les sous-domaines concernés utilisent HTTPS et que vous souhaitez inscrire le domaine dans la liste preload des navigateurs.

---

## Mise en production

1. Préparer PostgreSQL, Redis, un volume persistant pour `media/` et un reverse proxy HTTPS.
2. Définir les variables du `.env` de production : `DJANGO_DEBUG=0`, une clé secrète unique, domaines, PostgreSQL, `DJANGO_CACHE_URL` et `DJANGO_MEDIA_ROOT`. Si un reverse proxy est utilisé, définir `DJANGO_DERRIERE_PROXY=1` et `DJANGO_TRUSTED_PROXY_IPS`.
3. `python manage.py check --deploy` (corriger les avertissements applicables ; `security.W005` et `security.W021` correspondent aux choix HSTS décrits ci-dessus).
4. `python manage.py migrate`
5. `python manage.py collectstatic`
6. `python manage.py createsuperuser`
7. Dans le back-office :
   - régler le numéro WhatsApp et les pays livrés ;
   - régler les tarifs de livraison ;
   - retirer les données d'exemple ;
   - télécharger régulièrement une sauvegarde (Réglages du site → Maintenance).

   Le volume défini par `DJANGO_MEDIA_ROOT` (photos des produits) se sauvegarde à part.
