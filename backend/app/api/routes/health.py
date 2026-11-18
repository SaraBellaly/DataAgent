"""
Endpoints de health check pour vérifier l'état de l'application et de PostgreSQL.
"""
from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Dict, Any

from app.db.connection import check_db_connection, get_db_info

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Réponse de santé de l'application."""
    status: str
    message: str


class DatabaseHealthResponse(BaseModel):
    """Réponse de santé de la connexion PostgreSQL."""
    database: str
    status: str
    details: Dict[str, Any] | None = None


@router.get("", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """
    Vérifier l'état général de l'application.

    Returns:
        HealthResponse: Statut de l'application
    """
    return HealthResponse(
        status="healthy",
        message="AI Database Engineer API is running"
    )


@router.get("/db", response_model=DatabaseHealthResponse)
async def database_health():
    """
    Vérifier la connexion à PostgreSQL (sans exposer d'informations sensibles).

    Vérifie :
    - La connexion au serveur PostgreSQL
    - L'accès à la base 'immo' avec le rôle 'analyst_ro'
    - Les informations non-sensibles (version, nombre de tables)

    Returns:
        DatabaseHealthResponse: Statut de la connexion et informations de base

    Raises:
        HTTPException: 503 si la connexion échoue
    """
    is_connected = await check_db_connection()

    if not is_connected:
        return DatabaseHealthResponse(
            database="immo",
            status="disconnected",
            details={"error": "Unable to connect to PostgreSQL"}
        )

    # Récupérer les informations de la base
    db_info = await get_db_info()

    return DatabaseHealthResponse(
        database="immo",
        status="connected",
        details=db_info
    )
