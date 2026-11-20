"""
Cloisonnement des deux rôles (fiche, section 6.2) et endpoints de base.
"""
import psycopg
import pytest

from app.core.config import settings
from app.db.connection import pool_app, pool_ro

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("table", ["app.users", "app.sessions", "app.historique"])
def test_analyst_ro_ne_lit_pas_les_comptes_ni_l_historique(_app_started, table):
    with pool_ro.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"SELECT * FROM {table} LIMIT 1")


def test_app_agent_ne_lit_pas_les_donnees_metier(_app_started):
    with pool_app.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM immo.insee_communes LIMIT 1")


def test_app_agent_ne_modifie_pas_la_structure(_app_started):
    with pool_app.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE app.intrus (id int)")


def test_roles_utilises(_app_started):
    with pool_ro.connection() as conn:
        assert conn.execute("SELECT current_user").fetchone()[0] == settings.analyst_ro_user
    with pool_app.connection() as conn:
        assert conn.execute("SELECT current_user").fetchone()[0] == settings.app_agent_user


def test_racine_et_health(client):
    assert client.get("/api").json()["status"] == "running"
    assert client.get("/health").json()["status"] == "healthy"
    db = client.get("/health/db").json()
    assert db["status"] == "connected"
    assert db["details"]["user"] == "analyst_ro"


def test_pas_de_cors(client):
    r = client.options("/", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
