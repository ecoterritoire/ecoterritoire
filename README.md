# Ecoterritoire API

API FastAPI avec PostgreSQL/PostGIS et InfluxDB pour le développement local.

## Démarrage avec Docker Compose

Prérequis: Docker et Docker Compose.

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Le dashboard est disponible sur <http://localhost:8080> et l'API sur <http://localhost:8000>.

Le dashboard de développement utilise la clé publique `eco_public_dashboard_dev`
définie dans `client-web/app.js` et initialisée par `sql/seed_postgres.sql`.
Le seed initialise également la clé de démonstration mobile
`eco_mobile_client_dev`. Ces deux clés sont réservées au développement et ne
doivent pas être utilisées en production.
Cette clé est visible par tout visiteur et ne doit jamais être considérée comme
un secret ni réutilisée en production.

RedisInsight est disponible sur <http://localhost:5540> en développement.

### Environnements Docker

La configuration commune est dans `docker-compose.yml`.

Développement :

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Cet environnement expose les bases sur la machine hôte, active `--reload` et
inclut RedisInsight.

Production :

```bash
cp .env.prod.example .env
# Remplacez toutes les valeurs secrètes dans .env
docker compose --env-file .env -f docker/example/docker-compose.yml up -d
```

Les images de production sont publiées automatiquement dans GitHub Container
Registry par GitHub Actions après un push sur `main`. Pour les utiliser sans
rebuild local, connectez Docker à GHCR puis définissez le préfixe d'image et le
tag à déployer :

```bash
echo "$CR_PAT" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin
export GHCR_IMAGE_PREFIX=ghcr.io/ecoterritoire/ecoterritoire
export IMAGE_TAG=latest
docker compose --env-file .env -f docker/example/docker-compose.yml pull
docker compose --env-file .env -f docker/example/docker-compose.yml up -d
```

Le workflow CI exécute les tests avec couverture et l'analyse SonarQube sur les
pull requests. Configurez les secrets GitHub `SONAR_TOKEN` et `SONAR_HOST_URL`,
et activez le Quality Gate SonarQube comme règle obligatoire de la branche
`main`. Les images `api`, `web` et `db` sont publiées dans GHCR après le
passage de cette CI sur `main`.

La production n'expose pas PostgreSQL, InfluxDB ou Redis directement. Elle
n'active pas `--reload`, utilise plusieurs workers API, redémarre les services
automatiquement et n'inclut pas RedisInsight.

Un script simplifie ces commandes :

```bash
./script/docker.sh dev
BUILD=1 ./script/docker.sh dev
./script/docker.sh prod
ENV=dev ./script/docker.sh down
ENV=prod ./script/docker.sh logs
```

Le développement reste au premier plan pour afficher les logs. La production
démarre en arrière-plan. Le script ne supprime jamais les volumes de données.

- Documentation Swagger: <http://localhost:8000/docs>
- Vérification: <http://localhost:8000/health>

Endpoints de données:

```text
GET /stations
GET /pollutants
GET /pollution/map?day=2025-01-01&pollutant=NO
GET /pollution/timeline?start=2025-01-01&stop=2025-12-31&pollutant=NO&code_site=FR01011
```

La librairie partagée dans `lib/` centralise la configuration, les connexions et les requêtes PostgreSQL/InfluxDB utilisées par l'API et les scripts d'importation.

L'API utilise `db:5432` et `influxdb:8086` dans le réseau Compose. Depuis la machine hôte, PostgreSQL est accessible sur `localhost:5433` et InfluxDB sur `localhost:8086`.

## Importer les données

Le script télécharge les CSV journaliers, écrit les agrégations dans InfluxDB et synchronise les métadonnées de station dans PostgreSQL.

Depuis l'hôte, après avoir démarré les bases:

```bash
python script/tout_importe.py
```

Ou depuis un conteneur du projet:

```bash
docker compose run --rm api python script/tout_importe.py
```

Les années sont définies dans `IMPORT_YEARS`, par exemple `2025,2026`. La source de pollution ne fournissant pas encore les coordonnées ou les codes INSEE, ces champs restent vides dans `stations` jusqu'à l'ajout d'une source géographique de référence.

Pour synchroniser les coordonnées officielles LCSQA des stations:

```bash
docker compose run --rm api python script/enrichir_stations.py
```

Le référentiel utilise le même code Geod'air que les CSV de pollution et met à jour la géométrie PostGIS. Quand tous les polluants sont sélectionnés, la carte utilise un indice relatif normalisé par polluant ; avec un polluant précis, elle utilise directement sa valeur. Ces couleurs ne remplacent pas encore les seuils réglementaires propres à chaque polluant.

## Démarrage de l'API hors Docker

Pour lancer uniquement PostgreSQL dans Docker et Uvicorn localement:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
DATABASE_URL=postgresql://ecoterritoire:ecoterritoire@localhost:5433/ecoterritoire \
INFLUXDB_URL=http://localhost:8086 \
uvicorn app.main:app --reload
```

Les identifiants par défaut sont modifiables dans `.env`.

## Authentification

Les routeurs protégés utilisent la dépendance FastAPI `get_current_token` définie dans
`app/security/auth.py`. Le token est vérifié dans PostgreSQL via `lib.db`; aucun
utilisateur ou token n'est conservé en mémoire.

Les validations réussies sont mises en cache dans Redis pendant 60 secondes
(`AUTH_CACHE_TTL_SECONDS`). PostgreSQL reste la source de vérité : si Redis est
indisponible, l'API vérifie directement PostgreSQL. Une révocation doit invalider
la clé Redis du token, ou attendre l'expiration du TTL.

RedisInsight est disponible en développement sur
<http://localhost:5540>. Pour ajouter la connexion Redis dans l'interface,
utilisez l'hôte `redis`, le port `6379` et la base `0`. Redis n'est pas exposé
directement sur l'hôte ; RedisInsight y accède via le réseau Docker.

- **Format requis** : En-tête HTTP `Authorization: Bearer <votre_token>`
- **Sécurité et Hachage** : Les tokens bruts ne sont jamais stockés en clair. La dépendance d'authentification calcule le hash **SHA-256** du token et valide son existence et son statut actif dans la table PostgreSQL `api_tokens`.
- **Routes publiques** : `/health`, `/docs`, `/redoc`, `/openapi.json`, `/auth/token`.
- **Création d'un token** : `POST /auth/token` (alias historique : `POST /auth/tokens`).

### Table PostgreSQL `api_tokens`

La table `api_tokens` contient uniquement les informations nécessaires à la
validation des tokens :

| Colonne | Rôle |
| --- | --- |
| `id` | Identifiant interne |
| `token_hash` | Hash SHA-256 unique du token, jamais le token brut |
| `description` | Description du client ou de l'usage |
| `created_at` | Date de création |
| `last_used_at` | Dernière validation effectuée via PostgreSQL |
| `is_active` | Permet de révoquer un token |

Elle est définie dans `sql/script_postgres.sql` et reste initialisée de manière
idempotente par `lib.db.init_db()` pour les installations existantes.

Les endpoints sont séparés par domaine dans `app/routes/` :
`auth.py`, `stations.py`, `pollutants.py`, `pollution.py` et `measurements.py`.

### Back-office API

Le back-office est disponible à l'adresse <http://localhost:8000/admin>.
Le compte de démonstration est `admin` / `admin`, créé par
`sql/seed_postgres.sql`. Ce mot de passe doit être changé ou le compte désactivé
avant toute mise en production.

La page est rendue par FastAPI avec Jinja2 depuis `app/templates/admin.html`.
Ses fichiers CSS et JavaScript sont servis par FastAPI depuis `app/static/`.

Le back-office utilise les routes protégées suivantes :

- `POST /admin/login` : connexion administrateur et création d'un token lié à l'utilisateur ;
- `GET /admin/tokens` : liste paginée des clés, triées par date de création ;
- `GET /admin/stats` : nombre de clés totales, actives et utilisations cumulées.

Les requêtes SQL du back-office sont regroupées dans
`lib/admin.py`. La table `app_users` contient le compte, son hash de mot de
passe PBKDF2, son rôle et son statut. La table `api_tokens` référence
uniquement les clés d'accès à l'API. Les sessions temporaires du back-office
sont stockées séparément dans `admin_sessions`, expirent après
`ADMIN_SESSION_TTL_SECONDS` (8 heures par défaut), et les sessions expirées ou
révoquées sont nettoyées automatiquement. La déconnexion les révoque
immédiatement.
éventuellement l'utilisateur qui a créé le token et conserve `usage_count`.

### Générer un token

#### Option 1 : Via le script utilitaire
```bash
python scripts/create_token.py "Mon premier token"
```
ou directement :
```bash
python -m lib.db "Mon premier token"
```

#### Option 2 : Via l'endpoint public `/auth/token`
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"description": "Client mobile"}'
```

### Effectuer des requêtes authentifiées

```bash
curl -H "Authorization: Bearer <votre_token>" http://localhost:8000/measurements
```

Dans l'interface Swagger (<http://localhost:8000/docs>), cliquez sur le bouton vert **Authorize** en haut à droite et renseignez votre token.