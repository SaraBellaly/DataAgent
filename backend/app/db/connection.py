"""
Gestion des connexions PostgreSQL avec SQLAlchemy.

Deux connexions distinctes :
1. engine_ro : lecture seule sur les données immobilières (DVF/INSEE) avec rôle analyst_ro
2. engine_app : lecture/écriture pour les données applicatives (users, history) - Phase 3.2+
"""
from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# Connexion LECTURE SEULE — Données immobilières (DVF/INSEE)
# ============================================================================

# Engine pour lecture seule avec analyst_ro
# pool_pre_ping=True : vérifie que la connexion est vivante avant utilisation
# connect_args : paramètres PostgreSQL
engine_ro = create_engine(
    settings.database_url_ro,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "options": "-c statement_timeout=30000",  # 30s timeout (cohérent avec analyst_ro)
        "application_name": "ai_database_engineer_api"
    },
    echo=settings.debug  # Log SQL si debug=True
)

# Event listener pour vérifier que la connexion est bien en lecture seule
@event.listens_for(engine_ro, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Vérifier et forcer le mode lecture seule sur la connexion."""
    cursor = dbapi_conn.cursor()
    # Vérifier le timeout configuré
    cursor.execute("SHOW statement_timeout")
    timeout = cursor.fetchone()[0]
    logger.debug(f"Connexion analyst_ro établie, timeout: {timeout}")
    cursor.close()


# SessionLocal pour lecture seule
SessionLocalRO = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_ro
)

# Base déclarative pour les modèles (si on veut lire les tables existantes)
BaseRO = declarative_base()


def get_db_ro() -> Generator[Session, None, None]:
    """
    Dépendance FastAPI pour obtenir une session de lecture seule.

    Usage dans les routes :
        @router.get("/communes")
        def list_communes(db: Session = Depends(get_db_ro)):
            ...
    """
    db = SessionLocalRO()
    try:
        yield db
    finally:
        db.close()


async def check_db_connection() -> bool:
    """
    Vérifie que la connexion à PostgreSQL fonctionne.

    Returns:
        bool: True si la connexion est OK, False sinon
    """
    try:
        with engine_ro.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.scalar()
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_db_info() -> dict:
    """
    Récupère les informations sur la base de données (sans données sensibles).

    Returns:
        dict: Informations sur la base (version PostgreSQL, base, schéma)
    """
    try:
        with engine_ro.connect() as conn:
            # Version PostgreSQL
            version_result = conn.execute(text("SELECT version()"))
            version = version_result.scalar()

            # Base de données et rôle courants
            db_result = conn.execute(text("SELECT current_database(), current_user"))
            current_db, current_user = db_result.one()

            # Comptage tables dans schéma immo
            count_result = conn.execute(text("""
                SELECT count(*)
                FROM information_schema.tables
                WHERE table_schema = 'immo' AND table_type = 'BASE TABLE'
            """))
            table_count = count_result.scalar()

            return {
                "status": "connected",
                "postgresql_version": version.split(",")[0] if version else None,
                "database": current_db,
                "user": current_user,
                "schema": "immo",
                "tables_count": table_count
            }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# Connexion LECTURE/ÉCRITURE — Données applicatives (future - Phase 3.2+)
# ============================================================================

# engine_app = None
# SessionLocalApp = None
# BaseApp = None

# def init_app_database():
#     """
#     Initialise la connexion aux données applicatives.
#     À appeler après configuration de APP_DB_* dans .env
#     """
#     global engine_app, SessionLocalApp, BaseApp
#
#     if not settings.database_url_app:
#         logger.warning("App database URL not configured")
#         return
#
#     engine_app = create_engine(
#         settings.database_url_app,
#         pool_pre_ping=True,
#         pool_size=5,
#         max_overflow=10,
#         echo=settings.debug
#     )
#
#     SessionLocalApp = sessionmaker(autocommit=False, autoflush=False, bind=engine_app)
#     BaseApp = declarative_base()
#
#     logger.info("App database connection initialized")
#
# def get_db_app() -> Generator[Session, None, None]:
#     """Dépendance FastAPI pour session données applicatives."""
#     if SessionLocalApp is None:
#         raise RuntimeError("App database not initialized")
#
#     db = SessionLocalApp()
#     try:
#         yield db
#     finally:
#         db.close()
