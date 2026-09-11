# Ecoterritoire API

API FastAPI avec PostgreSQL pour le développement local. PostgreSQL est le seul service de données lancé par Docker Compose; la bibliothèque InfluxDB est installée côté Python, sans conteneur InfluxDB.

## Démarrage avec Docker Compose

Prérequis: Docker et Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

L'API est disponible sur <http://localhost:8000>.

- Documentation Swagger: <http://localhost:8000/docs>
- Vérification: <http://localhost:8000/health>

L'API utilise `db` comme nom d'hôte PostgreSQL dans le réseau Compose. Depuis la machine hôte, PostgreSQL est accessible sur `localhost:5432`.

## Démarrage de l'API hors Docker

Pour lancer uniquement PostgreSQL dans Docker et Uvicorn localement:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
DATABASE_URL=postgresql://ecoterritoire:ecoterritoire@localhost:5432/ecoterritoire uvicorn app.main:app --reload
```

Les identifiants par défaut sont modifiables dans `.env`.