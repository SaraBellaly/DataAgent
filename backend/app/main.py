"""
Application FastAPI : agent de gestion de base de données (projet 11).

Une seule application sert l'API (et, plus tard, les pages HTML) : pas de CORS, le cookie de
session SameSite=Strict n'est envoyé que par les pages de l'application elle-même.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, history, users
from app.core.config import settings
from app.db.connection import close_pools, open_pools

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage de %s v%s", settings.app_name, settings.app_version)
    open_pools()
    yield
    close_pools()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Inscription, connexion (session de 8 h par cookie HttpOnly + SameSite), "
        "historique personnel, puis agent d'analyse SQL en lecture seule."
    ),
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": settings.app_name, "version": settings.app_version, "status": "running",
            "docs": "/docs", "health": "/health"}


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(history.router)
# Agent (outils en lecture seule, question -> SQL) : à brancher à l'étape suivante
# app.include_router(agent.router)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    # Aucun détail interne (requête SQL, mot de passe, trace) n'est renvoyé au navigateur
    logger.error("Erreur non gérée sur %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Erreur interne du serveur."})
