from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import admin, auth, measurements, pollutants, pollution, stations
from lib.db import close_connection_pool, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_connection_pool()


app = FastAPI(title="Ecoterritoire API", lifespan=lifespan)
app.mount(
    "/admin/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="admin_static",
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(stations.router)
app.include_router(pollutants.router)
app.include_router(pollution.router)
app.include_router(measurements.router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
