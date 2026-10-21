# Eco Mart POS

Application de caisse en français pour Eco Mart Ltd, Royal Road, L’Escalier, Mauritius, BRN C26238002. Coordonnées extraites du document fourni. Montants MUR, dates Indian/Mauritius. Aucun produit fictif ni compte précréé dans la base réelle.

## Démarrer

Python 3.12 ou supérieur, sans dépendance externe :

```sh
cd /workspace/Eco-Mart-Ltd
python3 server.py
```

Sur le poste qui exécute le serveur, ouvrir le navigateur à l’adresse locale affichée par la commande. Créer un mot de passe administrateur d’au moins 10 caractères au premier démarrage. Le premier démarrage doit être effectué sur le poste de confiance. Le serveur écoute uniquement sur la boucle locale par défaut. Ne pas exposer ce serveur HTTP directement sur Internet. Une utilisation distante nécessite HTTPS et une configuration de déploiement adaptée. Le mot de passe est haché par PBKDF2, les sessions expirent après 12 heures et après redémarrage.

Variables facultatives : `PORT` (8000), `HOST` (127.0.0.1), `POS_DB` (data/pos.sqlite3). La base doit rester sur un disque local persistant accessible en écriture.

## Fonctions

- Catalogue : ajout, modification, catégories, prix TTC, stock, archivage et historique des mouvements.
- Caisse tactile : recherche, panier, quantités, scan, espèces avec monnaie rendue, carte et virement enregistrés après confirmation externe.
- Transaction SQLite atomique : calcul serveur en centimes, contrôle du stock, numéro de ticket unique et protection contre les doubles soumissions.
- Codes EAN-13 internes avec clé de contrôle et génération SVG sans service externe ; étiquettes 50 × 25 mm, 1 à 200 exemplaires. Préfixe 200 réservé ici à l’usage interne, sans prétention d’attribution GS1 pour vente dans d’autres commerces.
- Scan des codes numériques fabricants de 8, 12, 13 ou 14 chiffres. Impression d’étiquettes actuellement en EAN-13 uniquement.
- Tickets avec coordonnées, BRN, date, client facultatif, articles, paiement, total et TVA configurable. Les tickets gardent les coordonnées et prix d’origine.
- Historique, réimpression, remboursement intégral avec réintégration du stock et trace conservée. Effectuer également le remboursement effectif au client.
- Rapports par période, modes de paiement, remboursements à leur date effective, export CSV et alertes de stock.
- Sauvegarde SQLite cohérente téléchargeable depuis les paramètres.

## Utilisation et matériel

1. Ajouter les produits et le stock initial. Laisser le code vide pour générer un code interne, ou scanner le code fabricant dans le champ.
2. Imprimer une étiquette test à 100 %, sans en-têtes ni pieds de page du navigateur. Sélectionner dans le pilote le papier 50 × 25 mm et les marges nulles. Vérifier physiquement la lecture avant un tirage.
3. Configurer le scanner USB en mode clavier, clavier compatible avec le poste, suffixe **Entrée**. Dans Point de vente, placer le curseur dans le champ de recherche avant de scanner. Une pression Entrée ajoute le produit correspondant.
4. Encaisser, puis imprimer le ticket depuis son aperçu. Configurer le pilote de l’imprimante thermique en 58 ou 80 mm, selon le réglage de la caisse. Le pilote détermine le papier réel et la découpe.
5. Sauvegarder quotidiennement sur un autre support. Pour restaurer : arrêter le serveur, préserver la base actuelle, remplacer le fichier `data/pos.sqlite3` par la sauvegarde, puis redémarrer et vérifier les dernières ventes. Protéger les sauvegardes qui contiennent les données clients et le hash du mot de passe.

La TVA est désactivée par défaut : le document fourni ne contient pas de numéro de TVA. Faire confirmer le statut et les mentions fiscales avant exploitation ; renseigner numéro et taux pour l’activer. Les prix sont considérés TTC lorsque la TVA est activée.

## Validation

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Le test d’intégration utilise une base temporaire et exerce connexion, création produit, unicité des codes, vente, déduplication, insuffisance de stock et de paiement avec rollback, remboursement unique, TVA, conservation des tickets, sauvegarde, archivage et reconnexion. Aucun accès réseau externe n’est nécessaire au fonctionnement.

## Limites à traiter avant déploiement en magasin

Le matériel physique n’a pas été fourni : scanner, qualité des étiquettes, impression thermique et découpe doivent être validés sur les modèles retenus. L’ouverture automatique du tiroir, l’impression silencieuse et ESC/POS/ZPL nécessitent une passerelle ou un pilote adapté. Il n’existe pas encore d’intégration bancaire, de gestion des comptes caissiers et de leurs rôles, de clôtures de caisse, de retours partiels, de vente au poids, de remises ou de synchronisation entre magasins. La version actuelle utilise un seul compte administrateur ; les paiements carte et virement sont un enregistrement, pas un débit bancaire. Une mise en production demande ces décisions métier et la validation fiscale des reçus.

## Interface web

L’application propose maintenant un espace web responsive avec une navigation latérale, une page de connexion dédiée et un tableau de bord. Le tableau de bord affiche l’encaissement net du jour, le nombre de tickets, les produits actifs, les alertes de stock, les ventes brutes sur sept jours et les transactions récentes, à partir des données réelles de la base. Les raccourcis ouvrent directement la caisse, l’inventaire et les étiquettes.

L’interface s’adapte à l’ordinateur, à la tablette et au téléphone. Sur petit écran, le bouton « Voir le panier » permet d’accéder au panier sans parcourir tout le catalogue. La navigation est adressable par fragment (`#dashboard`, `#pos`, `#products`, etc.). Le bouton plein écran et l’aide rapide sont disponibles dans la barre supérieure. Le manifeste web permet l’affichage autonome lorsque le navigateur le prend en charge ; il ne fournit pas un mode de vente hors connexion au serveur.

Vérification optionnelle de l’interface, avec Playwright installé et Chromium disponible :

```sh
node tests/browser.cjs
```

Le test démarre son propre serveur avec une base temporaire, valide le parcours scan/paiement/impression, vérifie les sept écrans sur mobile et produit des captures sur ordinateur, tablette et téléphone. Il n’ajoute aucune donnée dans la base du magasin. Variables optionnelles : `CHROMIUM_PATH` pour le binaire Chromium et `POS_ARTIFACT_DIR` pour le dossier des captures.

## Hébergement Render

Le déploiement public est décrit dans [DEPLOY_RENDER.md](DEPLOY_RENDER.md). Le fichier `render.yaml` configure un service Python avec Gunicorn, un contrôle de santé et un disque persistant. Ce service et son disque nécessitent un plan payant, à confirmer dans votre compte Render. Le premier compte est protégé par un code d’activation généré dans Render. La préparation du dépôt ne constitue pas un déploiement réussi ; l’adresse publique doit être obtenue et testée après création du service.

Les étiquettes disposent aussi d’un téléchargement PDF vectoriel au format exact 50 × 25 mm, une page par étiquette. Dans le pilote, choisir le papier correspondant et une impression en taille réelle (100 %), sans en-têtes ni pieds de page. Le navigateur ne peut pas changer le format papier du pilote de l’imprimante.
