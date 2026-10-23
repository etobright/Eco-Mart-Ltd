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
- Historique, réimpression, retours partiels ou intégraux avec choix de la remise en stock et justificatifs liés à la vente. Effectuer également le remboursement effectif au client.
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

Le matériel physique n’a pas été fourni : scanner, qualité des étiquettes, impression thermique et découpe doivent être validés sur les modèles retenus. L’ouverture automatique du tiroir, l’impression silencieuse et ESC/POS/ZPL nécessitent une passerelle ou un pilote adapté. Il n’existe pas encore d’intégration bancaire, de gestion des comptes caissiers et de leurs rôles, de clôtures de caisse, de vente au poids, de remises manuelles ou de synchronisation entre magasins. La version actuelle utilise un seul compte administrateur ; les paiements carte et virement sont un enregistrement, pas un débit bancaire. Une mise en production demande ces décisions métier et la validation fiscale des reçus.

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

## Lecteur reconnu sur le PC mais pas sur le POS

Un scanner USB en mode clavier peut saisir `é`, `à`, `&`, etc. au lieu des chiffres si son pays clavier diffère de celui du terminal (QWERTY, AZERTY français ou belge). La caisse et le champ code-barres des produits reconnaissent les substitutions usuelles des touches numériques, tout en conservant les zéros initiaux. Les préfixes AIM EAN `]E0` / `]E4` et les suffixes Entrée/Tabulation sont pris en charge. Les lettres, URL et autres lectures non numériques ne sont pas converties arbitrairement en références produits.

Dans **Point de vente → Tester le lecteur**, scanner dans le champ puis valider : l’outil montre le texte reçu, le code interprété et le produit trouvé. Il ne modifie pas le panier. Si le produit est inconnu, le catalogue partagé est rechargé avant de signaler l’absence. Pour corriger le paramétrage matériel, sélectionner dans la notice du lecteur le pays clavier correspondant à celui du POS et le suffixe Entrée. Le focus doit être dans le champ de recherche pour les ventes.

Tests de normalisation : `node --test tests/scanner.test.cjs`. Le test navigateur couvre aussi un scan AZERTY et l’ajout depuis un deuxième poste.

Sur téléphone (jusqu’à 680 px de largeur), la navigation prend la forme d’une barre fixe en bas : **Accueil, Produits, Caisse, Ventes, Plus**. Le menu Plus ouvre un panneau avec Codes-barres, Rapports, Paramètres et Déconnexion. Le bouton du compte en haut ouvre le même panneau. Le panier reste au-dessus de la barre et les marges prennent en compte la zone de sécurité du téléphone. Les écrans PC et tablette conservent leur présentation existante. L’ouverture de la caisse sur téléphone ne déclenche pas automatiquement le clavier virtuel.

## Réactiver un produit archivé

Dans **Produits & stock**, les onglets **Actifs** et **Archivés** permettent de retrouver les deux listes. **Réactiver** remet le produit existant en vente avec le même identifiant, code-barres, stock et historique, puis ouvre sa fiche pour vérifier prix et quantité. Si un ajout utilise le code d’un produit archivé, le formulaire propose directement de le réactiver. Aucune vente passée et aucun mouvement de stock ne sont supprimés ou recréés pendant cette opération. L’archivage masque le produit en caisse et conserve son code pour cette réactivation.

## Supprimer définitivement un produit

**Archiver** masque un produit, garde son code réservé et permet sa réactivation. **Supprimer définitivement** retire réellement sa fiche des listes Actifs et Archivés et libère le code pour une nouvelle fiche.

Pour un produit actif : **Modifier → Supprimer définitivement**. Pour un produit archivé : bouton **Supprimer définitivement** dans l’onglet Archivés. La fenêtre indique le nom, le code et le stock retiré, puis demande de saisir `SUPPRIMER`. L’opération ne peut pas être annulée depuis l’application.

Les tickets et mouvements historiques restent conservés, avec les informations d’origine : la suppression du catalogue n’efface donc pas les codes figurant sur les anciens tickets. Un remboursement reste possible après suppression ; les produits supprimés ne sont pas remis en stock et la nouvelle fiche éventuellement créée avec le même code ne reçoit pas ce retour. Les identifiants de produits ne sont jamais réutilisés.

Au premier démarrage sur une ancienne base, la migration conserve les mouvements, rend leur lien produit facultatif et crée auparavant une sauvegarde locale `pos.sqlite3.before-delete-migration-*.bak` à côté de la base. Ne pas restaurer cette sauvegarde sur le service en cours sans arrêter celui-ci et préserver les ventes plus récentes. La migration et son redémarrage sont couverts par un test sur une base au format précédent.

## Remise automatique par quantité

Dès qu’une ligne du panier contient **6 unités ou plus d’un même produit**, une remise de **15 %** s’applique au total de cette ligne. Les autres produits ne sont pas remisés tant qu’ils n’atteignent pas eux-mêmes ce seuil. Exemple : 6 savons à Rs 100 et un riz à Rs 200 donnent **Rs 710** à payer (Rs 510 + Rs 200).

La remise est unique et ne se cumule pas à chaque groupe de six : 12 unités du même produit bénéficient de 15 %, pas de 30 %. Elle disparaît automatiquement quand la quantité repasse sous six. Chaque montant de remise est arrondi au centime sur sa ligne, puis additionné. La TVA incluse, le paiement, la monnaie et le remboursement reposent sur le montant effectivement facturé après remise. Le serveur vérifie le calcul et ignore les remises arbitraires envoyées par le navigateur.

Le panier et le ticket détaillent les remises ; l’export CSV contient le sous-total avant remise et la remise totale. Chaque vente conserve son calcul d’origine dans `pricing`, y compris pour les réimpressions et remboursements. L’ajout de ce champ ne recalcule pas les anciens tickets.

Tests de tarification : `node --test tests/pricing.test.cjs` et `python3 -m unittest discover -s tests -v`. Les tests couvrent les seuils 5/6/7/12, les paniers mixtes, les arrondis, les paiements, la TVA, la déduplication et les remboursements.


## Retours partiels et tickets de remboursement

Depuis **Ventes & tickets → Voir le ticket → Retour / Retirer des articles**, choisir la quantité de chaque article à retourner et cocher ou décocher **Remettre en stock**. Choisir le mode de remboursement, indiquer un motif facultatif et confirmer. Le bouton de sélection de toutes les quantités restantes permet un retour intégral ou le retour du solde après un premier retour partiel.

Le montant est calculé d’après le prix réellement payé sur le ticket, remise comprise, sans recalculer la promotion des articles conservés. Les centimes sont répartis sur les retours successifs afin que le remboursement de toutes les unités corresponde exactement au montant initialement payé. La TVA remboursée est répartie à partir de la TVA enregistrée lors de la vente.

La vente et son ticket original conservent leurs montants. Chaque retour possède une référence, une date, des quantités, un montant, un mode et un choix de remise en stock enregistrés dans un registre distinct. Le ticket de remboursement est imprimable immédiatement ou depuis l’historique des retours lié au ticket d’origine. Le statut devient **Retour partiel**, puis **Remboursée** quand toutes les unités ont été retournées. Les quantités déjà retournées ne peuvent pas l’être une seconde fois ; le serveur sérialise les opérations et déduplique les envois avec le même identifiant.

Les articles supprimés ne sont jamais recréés ni remis en stock sur une nouvelle fiche réutilisant le même code. Les anciens remboursements intégraux sont importés une seule fois dans le registre à leur date d’origine, sans nouvel effet sur le stock. Leur mode est indiqué comme mode de paiement d’origine, faute de choix de remboursement distinct dans l’ancien système.

Les rapports déduisent les retours à la date effective du remboursement. L’export des ventes indique les remboursements cumulés de chaque vente ; l’export des retours utilise la période de dates des retours eux-mêmes. L’application enregistre les opérations : effectuer également le remboursement réel en espèces ou via le terminal bancaire.
