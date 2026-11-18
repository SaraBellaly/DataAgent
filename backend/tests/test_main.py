"""
Tests pour les endpoints principaux de l'application.
"""
import pytest
from fastapi import status


def test_read_root(client):
    """Test de l'endpoint GET /"""
    response = client.get("/")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "running"
    assert "AI Database Engineer" in data["message"]


def test_docs_available(client):
    """Test que la documentation Swagger est accessible"""
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK


def test_redoc_available(client):
    """Test que la documentation ReDoc est accessible"""
    response = client.get("/redoc")
    assert response.status_code == status.HTTP_200_OK


def test_cors_headers(client):
    """Test que les headers CORS sont présents"""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
