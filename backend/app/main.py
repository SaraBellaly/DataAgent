"""
Application FastAPI : agent de gestion de base de données (projet 11).

Une seule application sert l'API ET l'interface React compilée (frontend/dist) : une seule origine,
donc pas de CORS, et le cookie de session SameSite=Strict n'est envoyé que par les pages de
l'application elle-même.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import agent, auth, conversations, dashboard, health, history, users, voice
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


@app.get("/api")
def api_root():
    return {"message": settings.app_name, "version": settings.app_version, "status": "running",
            "docs": "/docs", "health": "/health"}


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(history.router)
app.include_router(agent.router)
app.include_router(conversations.router)
app.include_router(dashboard.router)
app.include_router(voice.router)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    # Aucun détail interne (requête SQL, mot de passe, trace) n'est renvoyé au navigateur
    logger.error("Erreur non gérée sur %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Erreur interne du serveur."})


# ---------------------------------------------------------------------------
# Interface React compilée (production, image Docker). En développement, Vite la sert lui-même.
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")).resolve()

if (FRONTEND_DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Fichiers publics (favicon…) et, pour toute autre adresse, index.html : le routeur React
        affiche la bonne page (/historique, /conversations/12…). Les routes /api restent des 404 JSON."""
        if path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:   # pas de sortie du dossier
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})

