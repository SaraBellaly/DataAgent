"""
Fixtures pytest partagées pour les tests.

Sépare clairement les tests unitaires (avec mocks) des tests d'intégration (vraie BD).
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    """
    Client de test FastAPI pour requêtes HTTP.

    Crée une nouvelle instance d'app pour chaque test.

    Usage:
        def test_endpoint(client):
            response = client.get("/")
            assert response.status_code == 200
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_mock_db_connected(monkeypatch):
    """
    Client de test FastAPI avec mock de connexion PostgreSQL réussie.

    Utilise monkeypatch pour remplacer les fonctions du module connection
    AVANT l'import dans main.py (qui les utilise dans le lifespan).

    Usage:
        def test_health_with_mock(client_with_mock_db_connected):
            response = client_with_mock_db_connected.get("/health/db")
            assert response.status_code == 200
    """
    from app.db import connection

    async def mock_check_ok():
        return True

    async def mock_info_ok():
        return {
            "status": "connected",
            "postgresql_version": "PostgreSQL 16.16",
            "database": "immo",
            "user": "analyst_ro",
            "schema": "immo",
            "tables_count": 3
        }

    # Remplacer dans le module connection AVANT le démarrage
    monkeypatch.setattr(connection, "check_db_connection", mock_check_ok)
    monkeypatch.setattr(connection, "get_db_info", mock_info_ok)

    # Créer le TestClient avec les fonctions mockées
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_mock_db_disconnected(monkeypatch):
    """
    Client de test FastAPI avec mock de connexion PostgreSQL échouée.

    Utilise monkeypatch pour remplacer les fonctions du module connection
    AVANT l'import dans main.py (qui les utilise dans le lifespan).

    Usage:
        def test_db_error(client_with_mock_db_disconnected):
            response = client_with_mock_db_disconnected.get("/health/db")
            assert response.json()["status"] == "disconnected"
    """
    from app.db import connection

    async def mock_check_fail():
        return False

    async def mock_info_fail():
        return {
            "status": "error",
            "error": "Connection refused"
        }

    # Remplacer dans le module connection AVANT le démarrage
    monkeypatch.setattr(connection, "check_db_connection", mock_check_fail)
    monkeypatch.setattr(connection, "get_db_info", mock_info_fail)

    # Créer le TestClient avec les fonctions mockées
    with TestClient(app) as test_client:
        yield test_client
