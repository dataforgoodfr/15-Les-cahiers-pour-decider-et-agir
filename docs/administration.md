# Comptes et rôles de l'administration Wagtail

Ce document s'adresse aux administrateurs Wagtail. Il explique :
- comment ouvrir un compte à une personne ;
- comment lui permettre de choisir son mot de passe.

La plateforme a deux interfaces d'administration distinctes :
- **l'administration Wagtail**, sur `/admin/`, pour le contenu et les comptes. C'est celle dont parle ce document.
- **l'administration Django**, sur `/django-admin/`, réservée aux développeurs.

Aucun serveur mail n'est configuré, donc aucun mail ne part. Un administrateur Wagtail génère un lien de réinitialisation et le transmet lui-même.

## Rôles

| Rôle | Administration Wagtail | Administration Django | Comment on l'attribue |
| :--- | :--- | :--- | :--- |
| Développeur | tout | tout | compte développeur (identifiant `admin`), provisionné au démarrage |
| Administrateur Wagtail | tout, y compris créer des éditeurs et des modérateurs | aucun accès | case « Administrateur » dans l'administration Wagtail |
| Modérateur | créer, modifier et publier les pages | aucun accès | groupe `Moderators` dans l'administration Wagtail |
| Éditeur | créer et modifier les pages, puis les soumettre à modération | aucun accès | groupe `Editors` dans l'administration Wagtail |

Malgré son nom, la case « Administrateur » de Wagtail n'ouvre pas l'administration Django. Aucun réglage de l'administration Wagtail ne permet d'y donner accès. Pour savoir qui détient le compte développeur, voir [`deploiement.md`](deploiement.md#5-comptes-dadministration).

## Accueillir une personne

La procédure est la même en staging et en prod. Elle se fait une seule fois, car la base n'est pas recréée à chaque déploiement.

1. **Créer le compte.** Dans l'administration Wagtail, ouvrir **Paramètres → Utilisateurs → Ajouter un utilisateur**. Le prénom et le nom sont obligatoires. Aucun mot de passe n'est demandé : le compte ne permet pas encore de se connecter.
2. **Choisir le rôle.** Cocher le groupe `Editors` ou `Moderators`, ou bien la case « Administrateur ».
3. **Générer le lien.** Dans la liste des utilisateurs, sur la ligne du compte, choisir **Plus → Lien de réinitialisation**, puis copier le lien.
4. **Transmettre le lien** à la personne, et à elle seule, par un canal privé. Le lien :
   - expire après 3 jours ;
   - ne sert qu'une fois ;
   - mène à la page où la personne choisit son mot de passe.

**Qui fait quoi :**
- **Les administrateurs Wagtail** sont créés par un développeur, connecté avec le compte développeur. C'est le cas en prod comme en staging : aucun administrateur Wagtail n'est provisionné par défaut.
- **Les éditeurs et modérateurs** sont créés par un administrateur Wagtail, sans attendre un développeur.
- **Un administrateur Wagtail ne peut générer de lien que pour un éditeur ou un modérateur.** Il ne peut pas prendre la main sur le compte d'un autre administrateur Wagtail, ni sur celui d'un développeur.

## Mot de passe oublié, lien égaré

- **« Mot de passe oublié »**, sur la page de connexion de l'administration Wagtail, invite à demander un lien :
  - à un administrateur Wagtail pour un éditeur ou un modérateur ;
  - à un développeur pour un administrateur Wagtail.
- **Un lien envoyé à la mauvaise personne** reste valide jusqu'à son expiration. Générer un nouveau lien n'annule pas l'ancien. Pour le neutraliser, la bonne personne doit choisir son mot de passe au plus vite : tout changement de mot de passe invalide tous les liens émis auparavant.
- **Pour changer son propre mot de passe,** passer par **Compte** dans le menu de l'administration Wagtail. Le bouton de lien n'apparaît jamais sur son propre compte.
