from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.database import Base, engine
from app.core.config import get_settings
from app.models import *  # noqa: F401,F403 - importing registers all ORM tables with Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initial scaffold uses SQLAlchemy metadata; replace with Alembic migrations as schema evolves.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MarketPulse API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "marketpulse-api"}
