# Déployer Eco Mart sur Render

Le Blueprint `render.yaml` déploie le serveur Python avec Gunicorn et une base SQLite sur un disque persistant de 1 Go. Il conserve un seul processus applicatif et une seule instance : ne pas augmenter le nombre de workers ou d’instances avec ce stockage. Le plan Starter et le disque sont payants ; vérifier le tarif affiché par Render avant de créer le service.

## Création

1. Connecter votre compte Render à GitHub et autoriser le dépôt `etobright/Eco-Mart-Ltd`.
2. Dans Render, créer un **Blueprint** à partir de ce dépôt, branche `main`. Render doit détecter `render.yaml` à la racine.
3. Vérifier le service `eco-mart-pos`, le plan, la région Frankfurt et le disque monté sur `/var/data`, puis confirmer dans Render.
4. Attendre la réussite du déploiement et du contrôle `/api/health`. Utiliser l’adresse HTTPS indiquée par Render dans la page du service. Aucun nom de domaine public n’est attribué par les fichiers locaux.
5. Dans la section **Environment** du service, consulter la valeur générée pour `POS_SETUP_TOKEN`. Ne pas la publier ni l’envoyer par chat. Sur la page de création du compte, utiliser ce code d’activation puis choisir votre propre mot de passe administrateur.

Le code d’activation empêche un visiteur de créer le compte avant vous. Les cookies de connexion utilisent `Secure`, `HttpOnly` et `SameSite=Strict` en mode public. Le redémarrage du processus déconnecte les sessions ; il conserve les données sur le disque.

## Vérification après déploiement

- La page d’accueil HTTPS et `/api/health` répondent correctement.
- La création du compte sans code d’activation est refusée.
- Après connexion, ajouter un produit, enregistrer une vente test, imprimer un reçu et vérifier le stock. Effectuer le remboursement de la vente test pour conserver une trace cohérente.
- Télécharger une sauvegarde, redémarrer le service et vérifier que les produits et tickets sont toujours présents.
- Valider physiquement les imprimantes et le scanner sur le poste de caisse.

Le disque Render n’est pas une sauvegarde externe : télécharger régulièrement une copie depuis Paramètres. Le service ne sera pas utilisable pendant une coupure Internet au magasin. Une migration des éventuelles données locales doit être effectuée séparément ; le déploiement Git ne transfère pas `data/pos.sqlite3`.

## Configuration manuelle équivalente

- Runtime : Python 3.12.14
- Build : `pip install -r requirements.txt`
- Start : `gunicorn --config gunicorn.conf.py wsgi:application`
- Health check : `/api/health`
- `POS_DB=/var/data/pos.sqlite3`
- `POS_PUBLIC=1`
- `POS_SETUP_TOKEN` : secret aléatoire d’au moins 24 caractères, défini dans Render.
- Disque persistant : montage `/var/data`, 1 Go.

Le code d’activation n’est jamais enregistré dans Git. Ne pas démarrer une instance publique avec `python server.py` : utiliser la commande Gunicorn ci-dessus. Render fournit HTTPS ; ne pas exposer le port Gunicorn directement au public.
