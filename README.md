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

## Authentification et Middleware

L'API utilise un middleware FastAPI (`AuthTokenMiddleware`) qui intercepte et sécurise toutes les opérations de l'API.

- **Format requis** : En-tête HTTP `Authorization: Bearer <votre_token>`
- **Sécurité et Hachage** : Les tokens bruts ne sont jamais stockés en clair. Le middleware calcule le hash **SHA-256** du token et valide son existence et son statut actif dans la table PostgreSQL `api_tokens`.
- **Routes publiques exemptées** : `/health`, `/docs`, `/redoc`, `/openapi.json`, `/auth/tokens`.

### Générer un token

#### Option 1 : Via le script utilitaire
```bash
python scripts/create_token.py "Mon premier token"
```
ou directement :
```bash
python -m app.db "Mon premier token"
```

#### Option 2 : Via l'endpoint public `/auth/tokens`
```bash
curl -X POST http://localhost:8000/auth/tokens \
  -H "Content-Type: application/json" \
  -d '{"description": "Client mobile"}'
```

### Effectuer des requêtes authentifiées

```bash
curl -H "Authorization: Bearer <votre_token>" http://localhost:8000/measurements
```

Dans l'interface Swagger (<http://localhost:8000/docs>), cliquez sur le bouton vert **Authorize** en haut à droite et renseignez votre token.