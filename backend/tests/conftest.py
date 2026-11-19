"""
Fixtures partagées. Les tests utilisent la vraie base PostgreSQL (rôles analyst_ro et app_agent),
lue dans le .env racine. Les comptes de test ont des emails pytest-…@example.com et sont
supprimés à la fin de la session de tests.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.connection import pool_app
from app.main import app

TEST_PASSWORD = "Motdepasse-de-test-1"


@pytest.fixture(scope="session")
def _app_started():
    # Une seule exécution du lifespan : les pools psycopg ne se rouvrent pas après fermeture
    with TestClient(app) as c:
        yield c
    # (le nettoyage est fait dans _cleanup_test_users, avant la fermeture des pools)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_users(_app_started):
    yield
    with pool_app.connection() as conn:
        conn.execute("DELETE FROM app.users WHERE email LIKE 'pytest-%%@example.com'")


@pytest.fixture
def client(_app_started):
    """Client HTTP neuf (sans cookie) à chaque test, sur la même application.
    Sans `with` : le lifespan (ouverture des pools) a déjà été exécuté par _app_started."""
    c = TestClient(app)
    yield c
    c.close()


@pytest.fixture
def new_client(_app_started):
    """Fabrique de clients indépendants (un navigateur par utilisateur)."""
    clients = []

    def make():
        c = TestClient(app)
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.close()


def unique_email() -> str:
    return f"pytest-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def registered(client):
    """Compte de test inscrit : (email, mot de passe)."""
    email = unique_email()
    r = client.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD})
    assert r.status_code == 201, r.text
    return email, TEST_PASSWORD
