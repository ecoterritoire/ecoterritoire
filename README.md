# Ecoterritoire API

API FastAPI avec PostgreSQL/PostGIS et InfluxDB pour le développement local.

## Démarrage avec Docker Compose

Prérequis: Docker et Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Le dashboard est disponible sur <http://localhost:8080> et l'API sur <http://localhost:8000>.

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