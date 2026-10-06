#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILES=(-f docker-compose.yml)

usage() {
  cat <<'EOF'
Usage:
  ./script/docker.sh dev       Demarrer l'environnement de developpement
  ./script/docker.sh prod      Demarrer l'environnement de production
  ./script/docker.sh down      Arreter l'environnement selectionne
  ./script/docker.sh logs      Afficher les logs de l'environnement selectionne
  ./script/docker.sh ps        Afficher l'etat des services

Variables:
  ENV=dev|prod                 Environnement utilise par down, logs et ps
  BUILD=1                      Reconstruire les images pour dev
EOF
}

environment="${ENV:-dev}"
action="${1:-}"

case "$environment" in
  dev|prod)
    if [[ "$environment" == "dev" ]]; then
      COMPOSE_FILES+=(-f docker-compose.dev.yml)
    else
      COMPOSE_FILES=(-f docker/example/docker-compose.yml)
    fi
    ;;
  *)
    echo "Environnement invalide: $environment (attendu: dev ou prod)" >&2
    exit 2
    ;;
esac

case "$action" in
  dev|prod)
    if [[ "$action" != "$environment" ]]; then
      if [[ "$action" == "dev" ]]; then
        COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.dev.yml)
      else
        COMPOSE_FILES=(-f docker/example/docker-compose.yml)
      fi
    fi
    if [[ "$action" == "prod" ]]; then
      docker compose --env-file .env "${COMPOSE_FILES[@]}" pull
      docker compose --env-file .env "${COMPOSE_FILES[@]}" up -d
    else
      build_args=()
      [[ "${BUILD:-0}" == "1" ]] && build_args+=(--build)
      docker compose "${COMPOSE_FILES[@]}" up "${build_args[@]}"
    fi
    ;;
  down)
    docker compose "${COMPOSE_FILES[@]}" down
    ;;
  logs)
    docker compose "${COMPOSE_FILES[@]}" logs -f
    ;;
  ps)
    docker compose "${COMPOSE_FILES[@]}" ps
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
