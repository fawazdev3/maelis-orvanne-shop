# Maélis Orvanne Shop — étape 1 : projet et back-office

Site de la boutique en **Django + Bootstrap 5 + JavaScript**.
Cette étape contient le **back-office sur mesure** (aux couleurs bordeaux et or de la marque) pour gérer :

- les **catégories** (Thés, puis tout ce que vous ajouterez) ;
- les **produits** : nom, photo, description, prix, **prix promo** (prix barré et pourcentage de remise calculés automatiquement), en stock ou en rupture, visible ou caché, mis en avant sur l'accueil ;
- les **commandes** : liste filtrable par statut, détail, changement de statut (nouvelle → confirmée → en livraison → livrée / annulée), note interne, bouton pour écrire au client sur WhatsApp ;
- le **paiement à la livraison** : le client paie au livreur, en espèces ou par Mobile Money. Un bouton « Payée » marque la commande comme encaissée (la date est enregistrée), et l'onglet « À encaisser » liste les commandes pas encore payées ;
- un **tableau de bord** : nouvelles commandes, argent encaissé ce mois, montant restant à encaisser, graphique des ventes sur 30 jours, ruptures de stock.

> **Pourquoi la page Commandes est vide ?** Les commandes viendront du site public, construit à l'étape 2. En attendant, lance `donnees_exemple.bat` pour voir une commande de test.

Le site public (catalogue, panier, envoi de la commande sur WhatsApp) arrive à l'**étape 2**. Pour l'instant, l'adresse `/` affiche une page « bientôt en ligne ».

---

## 1. Installer et lancer sur ton PC (Windows)

### Le plus simple : les fichiers .bat (double-clic)

| Fichier | Rôle |
|---|---|
| `installer.bat` | **À lancer une seule fois** : crée l'environnement, installe Django, crée la base et ton compte gestionnaire |
| `lancer.bat` | Démarre le site et ouvre le back-office dans ton navigateur |
| `creer_compte.bat` | Crée un autre compte gestionnaire (par exemple pour ton collègue) |
| `donnees_exemple.bat` | Ajoute une catégorie, des produits et une commande « (exemple) » pour essayer |
| `tests.bat` | Lance les tests automatiques |

### Le fichier .env

Il contient tes réglages personnels : clé secrète, numéro WhatsApp de la boutique, base de données. Ouvre-le avec le Bloc-notes pour le modifier. Le fichier `.env.exemple` sert de modèle. **Ne partage jamais `.env`**, et ne le mets pas sur GitHub : il est déjà exclu dans `.gitignore`.

### Ou à la main, dans un terminal

Ouvre un terminal dans le dossier `maelis_orvanne`, puis :

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> Sur Linux ou macOS, remplace `venv\Scripts\activate` par `source venv/bin/activate`.

Pendant `createsuperuser`, choisis ton nom d'utilisateur et ton mot de passe : ce sont tes identifiants du back-office.

Ouvre ensuite **http://127.0.0.1:8000/gestion/** dans ton navigateur et connecte-toi.

### Essayer avec des données d'exemple (facultatif)

```bash
python manage.py donnees_exemple
```

Cette commande crée une catégorie, trois produits et une commande, tous marqués « (exemple) ». Supprime-les depuis le back-office quand tu as fini d'essayer.

### Lancer les tests

```bash
python manage.py test
```

---

## 2. Les adresses

| Adresse | Rôle |
|---|---|
| `/gestion/` | Back-office de la boutique (tableau de bord) |
| `/gestion/produits/` | Produits |
| `/gestion/categories/` | Catégories |
| `/gestion/commandes/` | Commandes |
| `/admin-technique/` | Administration Django de secours (dépannage seulement) |
| `/` | Site public (provisoire, construit à l'étape 2) |

Seuls les comptes « membres du personnel » (`is_staff`) peuvent entrer dans le back-office. Le compte créé avec `createsuperuser` l'est automatiquement. Pour ajouter ton collègue, crée-lui un compte dans `/admin-technique/` et coche « Statut équipe ».

---

## 3. Organisation du projet

```
maelis_orvanne/
├── config/                 Réglages et adresses du projet
│   ├── settings.py
│   └── urls.py
├── boutique/               Les données de la boutique
│   ├── models.py           Categorie, Produit, Commande, LigneCommande
│   ├── admin.py            Administration de secours
│   └── management/commands/donnees_exemple.py
├── gestion/                Le back-office sur mesure
│   ├── views.py            Pages du back-office
│   ├── forms.py            Formulaires (produit, catégorie, commande, connexion)
│   ├── urls.py
│   ├── decorators.py       Accès réservé aux gestionnaires
│   ├── templatetags/gestion_extras.py   Filtre « fcfa » (12 500 FCFA)
│   └── tests.py
├── templates/gestion/      Pages HTML du back-office
├── static/gestion/         CSS (charte bordeaux et or) et JavaScript
└── media/                  Photos des produits (créé automatiquement)
```

### Points techniques
- **Prix en FCFA**, nombres entiers.
- **Prix promo** : il doit être inférieur au prix normal (vérifié dans le formulaire). Le site affiche alors le prix barré et le pourcentage de remise.
- **Commandes** : chaque ligne garde une **copie** du nom et du prix du produit au moment de l'achat. Si tu modifies ou supprimes un produit plus tard, l'historique reste juste.
- **Numéros de commande** au format `MO-AAAAMMJJ-001`.
- **Catégories** : une catégorie qui contient encore des produits ne peut pas être supprimée, pour éviter de perdre des produits par erreur.
- **Numéro WhatsApp de la boutique** : à renseigner plus tard dans `config/settings.py` (`BOUTIQUE_WHATSAPP`) ou par la variable d'environnement du même nom. Il servira à l'étape 2.

---

## 4. Mise en ligne (plus tard)

En production, définis ces variables d'environnement :

```
DJANGO_SECRET_KEY=une-longue-cle-secrete
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=maelisorvanne.com,www.maelisorvanne.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://maelisorvanne.com,https://www.maelisorvanne.com
POSTGRES_DB=...  POSTGRES_USER=...  POSTGRES_PASSWORD=...  POSTGRES_HOST=...
```

Puis lance `python manage.py collectstatic` et `python manage.py migrate`. Pour PostgreSQL, installe aussi `psycopg[binary]`.

---

## 5. Prochaine étape

**Étape 2 : le site public**
- accueil avec le logo et les produits mis en avant ;
- catalogue par catégorie : photo, nom, prix (prix barré en promotion) et bouton « Ajouter au panier » ;
- panier : quantités et calcul automatique du total ;
- formulaire : nom, téléphone, ville, lieu de livraison ;
- commande **enregistrée dans le back-office** puis **envoyée sur WhatsApp**.
