#!/usr/bin/env bash
# plateforme/deploy_env.sh — déploiement manuel complet d'un environnement.
# Usage : CLEVER_APP_ID=… DJANGO_SECRET_KEY=… DJANGO_SUPERUSER_PASSWORD=… ./plateforme/deploy_env.sh staging
set -euo pipefail

# Exécute une commande sans interrompre le script si elle échoue.
# Les commandes clever « d'idempotence » échouent quand l'état est déjà atteint
# (« already linked », « No configuration to update »…) : on tolère ces échecs
# tout en conservant leur sortie d'erreur pour le débogage.
clever_ok() {
  if ! "$@"; then
    echo "[ignoré] état probablement déjà atteint : $*" >&2
  fi
}

ENV="${1:-staging}"
ORG="Les Cahiers pour Décider et Agir"

case "$ENV" in
  staging)
    ALIAS="staging"
    ENV_UP="STAGING"
    HOSTS="cahiers-staging.cleverapps.io"
    BUCKET="cahiers-staging-prive"
    PG_ADDON="staging_postgres"
    CELLAR_ADDON="staging_cellar_cahiers_citoyens"
    ;;
  prod)
    ALIAS="prod"
    ENV_UP="PROD"
    HOSTS="<domaines-prod>"
    BUCKET="<bucket-prod-prive>"
    PG_ADDON="production_postgres"
    CELLAR_ADDON="<cellar-prod-prive>"
    ;;
  *) echo "environnement inconnu : $ENV (staging|prod)" >&2; exit 1;;
esac

: "${CLEVER_APP_ID:?CLEVER_APP_ID manquant}"
: "${DJANGO_SECRET_KEY:?DJANGO_SECRET_KEY manquant}"
: "${DJANGO_SUPERUSER_PASSWORD:?DJANGO_SUPERUSER_PASSWORD manquant}"

# 1. Lier le dépôt à l'application existante (ne recrée rien)
clever_ok clever link "$CLEVER_APP_ID" --org "$ORG" --alias "$ALIAS"

# 2. Lier les add-ons existants (privé uniquement : pas de second Cellar)
clever_ok clever service link-addon "$PG_ADDON" --alias "$ALIAS"
clever_ok clever service link-addon "$CELLAR_ADDON" --alias "$ALIAS"

# 3. Force HTTPS
clever_ok clever config update --alias "$ALIAS" --enable-force-https

# 4. Variables d'environnement (idempotent : met à jour les valeurs)
clever env set DJANGO_ENV "$ENV_UP" --alias "$ALIAS"
clever env set DJANGO_SECRET_KEY "$DJANGO_SECRET_KEY" --alias "$ALIAS"
clever env set DJANGO_ALLOWED_HOSTS "$HOSTS" --alias "$ALIAS"
clever env set CC_APP_FOLDER plateforme --alias "$ALIAS"
clever env set CC_PYTHON_UV_RUN_COMMAND "uv run gunicorn config.wsgi" --alias "$ALIAS"
clever env set CC_POST_BUILD_HOOK "cd plateforme && uv run python manage.py collectstatic --noinput" --alias "$ALIAS"
clever env set CC_PRE_RUN_HOOK "cd plateforme && uv run python manage.py migrate --noinput && uv run python manage.py charger_chabin_extraits && uv run python manage.py initialiser_admin" --alias "$ALIAS"
clever env set DJANGO_SUPERUSER_USERNAME admin --alias "$ALIAS"
clever env set DJANGO_SUPERUSER_EMAIL admin@decider-agir.fr --alias "$ALIAS"
clever env set DJANGO_SUPERUSER_PASSWORD "$DJANGO_SUPERUSER_PASSWORD" --alias "$ALIAS"
clever env set CELLAR_BUCKET "$BUCKET" --alias "$ALIAS"
clever env set AWS_REQUEST_CHECKSUM_CALCULATION when_required --alias "$ALIAS"
clever env set AWS_RESPONSE_CHECKSUM_VALIDATION when_required --alias "$ALIAS"

# 5. Domaine
clever_ok clever domain add "$HOSTS" --alias "$ALIAS"

# 6. Déploiement (fatal : un échec ici est une vraie erreur)
clever deploy --alias "$ALIAS" --force --same-commit-policy rebuild

# 7. Seed (idempotent, relançable à chaque déploiement)
#    `clever ssh` nécessite une clé SSH enregistrée : clever ssh-keys add < clé.pub>
clever ssh --alias "$ALIAS" --instance any --app-home --command "cd plateforme && uv run python manage.py charger_communes"
# Seed des contributions (nécessite les sorties caviardées d'analyse/, hors repo) :
#   clever ssh --alias "$ALIAS" --instance any --app-home --command "cd plateforme && uv run python manage.py charger_corpus"
#   clever ssh --alias "$ALIAS" --instance any --app-home --command "cd plateforme && uv run python manage.py charger_contributions"
#   clever ssh --alias "$ALIAS" --instance any --app-home --command "cd plateforme && uv run python manage.py charger_extraits"
#   clever ssh --alias "$ALIAS" --instance any --app-home --command "cd plateforme && uv run python manage.py charger_chabin"
