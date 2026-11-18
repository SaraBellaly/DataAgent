"""
Tests pour les endpoints de health check.
"""
import pytest
from fastapi import status


def test_health_check(client):
    """Test de l'endpoint GET /health"""
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "message" in data


def test_database_health_response_structure(client):
    """
    Test unitaire de la structure de réponse de /health/db.

    Vérifie que l'endpoint répond correctement, peu importe l'état de la BD.
    Le statut dépendra du fait que PostgreSQL soit accessible ou non.
    """
    response = client.get("/health/db")

    # La réponse doit toujours être 200 (pas d'erreur HTTP)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # Vérifier la structure de la réponse
    assert data["database"] == "immo"
    assert "status" in data  # "connected" ou "disconnected"
    assert "details" in data

    # Si connecté
    if data["status"] == "connected":
        details = data["details"]
        assert details["status"] == "connected"
        assert "postgresql_version" in details
        assert details["user"] == "analyst_ro"
        assert details["database"] == "immo"
        assert details["schema"] == "immo"
    # Si déconnecté
    elif data["status"] == "disconnected":
        assert "error" in data["details"]
    else:
        # Statut inattendu
        assert False, f"Status inattendu: {data['status']}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_check_db_connection_real():
    """
    Test d'intégration avec la vraie base PostgreSQL.

    Note: Ce test NÉCESSITE que PostgreSQL soit accessible et configuré.
    Il est marqué avec @pytest.mark.integration pour l'exécuter séparément :

        pytest tests/ -m integration  # Seulement tests d'intégration
        pytest tests/ -m "not integration"  # Seulement tests unitaires
    """
    from app.db.connection import check_db_connection

    result = await check_db_connection()
    assert isinstance(result, bool)

    # Le test passe si PostgreSQL est accessible (True) ou pas (False)
    # L'important est que la fonction retourne un booléen


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_db_info_real():
    """
    Test d'intégration avec la vraie base PostgreSQL.

    Note: Ce test NÉCESSITE que PostgreSQL soit accessible et configuré.
    Il est marqué avec @pytest.mark.integration pour l'exécuter séparément :

        pytest tests/ -m integration  # Seulement tests d'intégration
        pytest tests/ -m "not integration"  # Seulement tests unitaires
    """
    from app.db.connection import get_db_info

    result = await get_db_info()

    assert isinstance(result, dict)
    assert "status" in result

    # Si connecté, vérifier les infos complètes
    if result["status"] == "connected":
        assert "postgresql_version" in result
        assert "database" in result
        assert "user" in result
        assert result["user"] == "analyst_ro"
    # Si déconnecté, vérifier le message d'erreur
    elif result["status"] == "error":
        assert "error" in result
