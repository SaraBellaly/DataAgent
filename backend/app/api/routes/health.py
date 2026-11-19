"""
Health checks : état de l'application et de la connexion PostgreSQL (analyst_ro).
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import connection

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    message: str


class DatabaseHealthResponse(BaseModel):
    database: str
    status: str
    details: dict[str, Any] | None = None


@router.get("", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="healthy", message="L'application fonctionne")


@router.get("/db", response_model=DatabaseHealthResponse)
def database_health():
    """Connexion à la base avec analyst_ro, sans exposer d'information sensible."""
    if not connection.check_db_connection():
        return DatabaseHealthResponse(database="immo", status="disconnected",
                                      details={"error": "Base de données indisponible"})
    return DatabaseHealthResponse(database="immo", status="connected", details=connection.get_db_info())
