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
  BUILD=1                      Reconstruire les images pour dev/prod
EOF
}

environment="${ENV:-dev}"
action="${1:-}"

case "$environment" in
  dev|prod)
    COMPOSE_FILES+=(-f "docker-compose.${environment}.yml")
    ;;
  *)
    echo "Environnement invalide: $environment (attendu: dev ou prod)" >&2
    exit 2
    ;;
esac

case "$action" in
  dev|prod)
    if [[ "$action" != "$environment" ]]; then
      COMPOSE_FILES=(-f docker-compose.yml -f "docker-compose.${action}.yml")
    fi
    build_args=()
    [[ "${BUILD:-0}" == "1" ]] && build_args+=(--build)
    if [[ "$action" == "prod" ]]; then
      docker compose "${COMPOSE_FILES[@]}" up -d "${build_args[@]}"
    else
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
