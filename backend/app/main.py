"""
Point d'entrée de l'API FastAPI.

AI Database Engineer - Backend API
Phase 3.1 : Infrastructure de base (health checks, connexion PostgreSQL)
"""
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.routes import health
# Routes futures (vides pour Phase 3.1)
# from app.api.routes import auth, users, history, agent

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle de l'application : startup et shutdown.

    Startup:
    - Vérifier la connexion PostgreSQL
    - Initialiser les connexions (si nécessaire)

    Shutdown:
    - Fermer les connexions proprement
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")

    # Vérifier la connexion à PostgreSQL
    from app.db.connection import check_db_connection
    db_ok = await check_db_connection()
    if db_ok:
        logger.info("✓ PostgreSQL connection OK (analyst_ro)")
    else:
        logger.warning("✗ PostgreSQL connection failed")

    yield

    # Shutdown
    logger.info("Shutting down application")


# Initialisation de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Backend API pour l'agent IA d'analyse SQL sur le marché immobilier français.

    **Phase 3.1** : Infrastructure de base
    - Health checks
    - Connexion PostgreSQL sécurisée (lecture seule avec analyst_ro)

    **Phases futures** :
    - Phase 3.2 : Authentification et gestion utilisateurs
    - Phase 3.3 : Historique des conversations
    - Phase 3.4 : Agent Text-to-SQL et exécution sécurisée
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints racine
# ============================================================================

@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """
    Endpoint racine : vérifier que l'API fonctionne.

    Returns:
        dict: Message de bienvenue et version
    """
    return {
        "message": "AI Database Engineer API",
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# ============================================================================
# Inclusion des routers
# ============================================================================

# Phase 3.1 : Health checks
app.include_router(health.router)

# Phase 3.2+ : Routes futures (décommentées plus tard)
# app.include_router(auth.router, prefix="/api/v1")
# app.include_router(users.router, prefix="/api/v1")

# Phase 3.3+ : Historique
# app.include_router(history.router, prefix="/api/v1")

# Phase 3.4+ : Agent IA
# app.include_router(agent.router, prefix="/api/v1")


# ============================================================================
# Gestion des erreurs globales
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Gestionnaire d'erreurs global pour éviter d'exposer les détails internes.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.debug:
        # En mode debug, retourner les détails
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__
            }
        )
    else:
        # En production, message générique
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal Server Error"}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
