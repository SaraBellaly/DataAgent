"""
Connexions PostgreSQL (psycopg 3), deux pools séparés :

- pool_ro  : rôle analyst_ro, lecture seule sur immo (outils de l'agent, health check).
             Il n'a aucun accès aux comptes ni à l'historique.
- pool_app : rôle app_agent, lecture et écriture sur le schéma app uniquement.
             Il n'exécute que des requêtes écrites par nous, toujours paramétrées.

Les pools sont ouverts au démarrage de l'application (lifespan de main.py).
"""
import logging
from typing import Any

from psycopg_pool import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

pool_ro = ConnectionPool(settings.conninfo_ro, min_size=1, max_size=5, open=False, name="analyst_ro")
pool_app = ConnectionPool(settings.conninfo_app, min_size=1, max_size=10, open=False, name="app_agent")


def open_pools() -> None:
    # wait=False : l'application démarre même si la base n'est pas encore prête
    for pool in (pool_ro, pool_app):
        if pool.closed:
            pool.open(wait=False)


def close_pools() -> None:
    for pool in (pool_ro, pool_app):
        if not pool.closed:
            pool.close()


def check_db_connection() -> bool:
    """True si analyst_ro peut se connecter et exécuter une requête."""
    try:
        with pool_ro.connection(timeout=5) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as exc:  # base arrêtée, mot de passe faux, délai dépassé
        logger.error("Connexion PostgreSQL (analyst_ro) impossible : %s", exc)
        return False


def get_db_info() -> dict[str, Any]:
    """Informations non sensibles sur la base, lues avec analyst_ro."""
    try:
        with pool_ro.connection(timeout=5) as conn:
            version, database, user = conn.execute(
                "SELECT split_part(version(), ',', 1), current_database(), current_user"
            ).fetchone()
            (tables_count,) = conn.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'immo' AND table_type = 'BASE TABLE'"
            ).fetchone()
        return {
            "status": "connected",
            "postgresql_version": version,
            "database": database,
            "user": user,
            "schema": "immo",
            "tables_count": tables_count,
        }
    except Exception as exc:
        logger.error("Lecture des informations de la base impossible : %s", exc)
        return {"status": "error", "error": "Base de données indisponible"}
