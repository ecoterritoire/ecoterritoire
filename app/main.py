from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.db import close_connection_pool, init_db
from app.routes import auth, measurements
from lib.middleware import AuthTokenMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise les tables de la base de donnees au demarrage et libere le pool a l'arret."""
    init_db()
    yield
    close_connection_pool()


app = FastAPI(title="Ecoterritoire API", lifespan=lifespan)

# Enregistrement du middleware d'authentification pour toutes les operations de l'API
app.add_middleware(AuthTokenMiddleware)

# Inclusion des routeurs modulaires
app.include_router(auth.router)
app.include_router(measurements.router)


def custom_openapi() -> dict[str, object]:
    """Personnalise le schema OpenAPI pour integrer l'authentification Bearer dans Swagger UI."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Ecoterritoire API",
        version="1.0.0",
        description="API FastAPI avec PostgreSQL et middleware d'authentification Bearer Token hache en SHA-256.",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Token",
            "description": "Fournir le token d'authentification (ex: eco_...)",
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Endpoint public de verification de sante de l'API."""
    return {"status": "ok"}
