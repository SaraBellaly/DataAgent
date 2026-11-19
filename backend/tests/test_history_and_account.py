"""
Historique cloisonné par utilisateur et suppression du compte (fiche, écran 4, Q10, Q15).
"""
import pytest

from app import repositories as repo
from app.core.config import settings
from app.db.connection import pool_app
from tests.conftest import TEST_PASSWORD, unique_email

pytestmark = pytest.mark.integration


def make_user(new_client):
    """Inscrit et connecte un utilisateur dans son propre client ; renvoie (client, id)."""
    c = new_client()
    email = unique_email()
    assert c.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD}).status_code == 201
    assert c.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD}).status_code == 204
    return c, c.get("/api/users/me").json()["id"]


def add_entry(user_id, question):
    with pool_app.connection() as conn:
        return repo.add_history(conn, user_id, question, "SELECT 1", "explication")


def test_historique_personnel(new_client):
    a, a_id = make_user(new_client)
    first = add_entry(a_id, "Prix au m² à Bordeaux en 2025 ?")
    second = add_entry(a_id, "et Toulouse ?")
    items = a.get("/api/history").json()
    assert [i["id"] for i in items] == [second, first]  # plus récent d'abord
    assert a.get(f"/api/history/{first}").json()["question"] == "Prix au m² à Bordeaux en 2025 ?"


def test_acces_croise_entre_deux_comptes(new_client):
    a, a_id = make_user(new_client)
    b, _ = make_user(new_client)
    entry = add_entry(a_id, "Question privée de A")

    assert b.get("/api/history").json() == []
    r = b.get(f"/api/history/{entry}")
    # Même réponse qu'un identifiant inexistant : l'existence de l'échange n'est pas révélée
    assert r.status_code == 404
    assert r.json() == b.get("/api/history/999999999").json() == {"detail": "Introuvable."}


def test_parametre_utilisateur_ignore(new_client):
    """L'identifiant vient de la session : un user_id ajouté par le navigateur ne change rien."""
    a, a_id = make_user(new_client)
    b, _ = make_user(new_client)
    add_entry(a_id, "Question privée de A")
    assert b.get("/api/history", params={"user_id": a_id}).json() == []


def test_suppression_exige_confirmation(new_client):
    a, _ = make_user(new_client)
    r = a.request("DELETE", "/api/users/me", json={"confirmation": False})
    assert r.status_code == 400
    assert a.get("/api/users/me").status_code == 200  # rien n'a été modifié
    assert a.request("DELETE", "/api/users/me", json={}).status_code == 422


def test_suppression_du_compte_avec_sessions_et_historique(new_client):
    a, a_id = make_user(new_client)
    add_entry(a_id, "Question à supprimer")
    token = a.cookies[settings.session_cookie_name]

    r = a.request("DELETE", "/api/users/me", json={"confirmation": True})
    assert r.status_code == 204

    with pool_app.connection() as conn:
        for table in ("users", "sessions", "historique"):
            column = "id" if table == "users" else "user_id"
            (n,) = conn.execute(f"SELECT count(*) FROM app.{table} WHERE {column} = %s", (a_id,)).fetchone()
            assert n == 0, table

    other = new_client()
    other.cookies.set(settings.session_cookie_name, token)
    assert other.get("/api/users/me").status_code == 401
