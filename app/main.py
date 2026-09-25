from fastapi import FastAPI

from app.routes import auth, measurements


app = FastAPI(title="Ecoterritoire API")
app.include_router(auth.router)
app.include_router(measurements.router)

