"""
Inscription, connexion, session, déconnexion, blocage (fiche de cadrage, sections 3, 5.1, Q10).
"""
import pytest

from app.core.config import settings
from app.db.connection import pool_app
from tests.conftest import TEST_PASSWORD, unique_email

pytestmark = pytest.mark.integration

COOKIE = settings.session_cookie_name


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Inscription
# ---------------------------------------------------------------------------
def test_inscription_cree_le_compte_sans_ouvrir_de_session(client):
    email = unique_email()
    r = client.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD})
    assert r.status_code == 201
    assert r.json()["email"] == email
    assert "password" not in r.text and "hash" not in r.text
    assert COOKIE not in r.cookies


def test_mot_de_passe_stocke_hache_argon2id(registered):
    email, password = registered
    with pool_app.connection() as conn:
        (h,) = conn.execute("SELECT password_hash FROM app.users WHERE email = %s", (email,)).fetchone()
    assert h.startswith("$argon2id$")
    assert password not in h


def test_email_normalise_en_minuscules(client):
    email = unique_email()
    r = client.post("/api/auth/register", json={"email": email.upper(), "password": TEST_PASSWORD})
    assert r.status_code == 201
    assert r.json()["email"] == email


def test_inscription_email_deja_utilise(client, registered):
    email, _ = registered
    r = client.post("/api/auth/register", json={"email": email, "password": "Autre-mot-de-passe"})
    assert r.status_code == 409
    assert "déjà utilisée" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"email": "pas-un-email", "password": TEST_PASSWORD},
    {"email": "pytest-court@example.com", "password": "court"},
    {"email": "pytest-x@example.com"},
    # Minimisation : aucun autre champ accepté (nom, téléphone…)
    {"email": "pytest-y@example.com", "password": TEST_PASSWORD, "fullname": "Jean"},
])
def test_inscription_entrees_invalides(client, body):
    assert client.post("/api/auth/register", json=body).status_code == 422


# ---------------------------------------------------------------------------
# Connexion et cookie
# ---------------------------------------------------------------------------
def test_connexion_pose_un_cookie_httponly_samesite_8h(client, registered):
    r = login(client, *registered)
    assert r.status_code == 204
    set_cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert f"max-age={8 * 3600}" in set_cookie
    assert client.get("/api/users/me").json()["email"] == registered[0]


def test_jeton_stocke_sous_forme_d_empreinte(client, registered):
    login(client, *registered)
    token = client.cookies[COOKIE]
    with pool_app.connection() as conn:
        rows = conn.execute(
            "SELECT s.token_hash FROM app.sessions s JOIN app.users u ON u.id = s.user_id WHERE u.email = %s",
            (registered[0],),
        ).fetchall()
    assert len(rows) == 1
    assert token.encode() not in bytes(rows[0][0])
    assert len(rows[0][0]) == 32


def test_message_identique_email_inconnu_ou_mot_de_passe_faux(client, registered):
    email, _ = registered
    faux_mdp = login(client, email, "mauvais-mot-de-passe")
    inconnu = login(client, unique_email(), "mauvais-mot-de-passe")
    assert faux_mdp.status_code == inconnu.status_code == 401
    assert faux_mdp.json() == inconnu.json() == {"detail": "Email ou mot de passe incorrect."}


def test_acces_sans_session_refuse(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/history").status_code == 401


def test_cookie_invente_refuse(client):
    client.cookies.set(COOKIE, "jeton-invente")
    assert client.get("/api/users/me").status_code == 401


# ---------------------------------------------------------------------------
# Déconnexion et expiration
# ---------------------------------------------------------------------------
def test_deconnexion_invalide_la_session_cote_serveur(client, new_client, registered):
    login(client, *registered)
    token = client.cookies[COOKIE]
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    # Même en rejouant l'ancien cookie (vol ou copie), la session ne vaut plus rien
    other = new_client()
    other.cookies.set(COOKIE, token)
    assert other.get("/api/users/me").status_code == 401


def test_deconnexion_sans_session(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_session_expiree_refusee(client, registered):
    login(client, *registered)
    with pool_app.connection() as conn:
        conn.execute(
            "UPDATE app.sessions SET created_at = now() - interval '9 hours', "
            "expires_at = now() - interval '1 hour' "
            "WHERE user_id = (SELECT id FROM app.users WHERE email = %s)",
            (registered[0],),
        )
    assert client.get("/api/users/me").status_code == 401


# ---------------------------------------------------------------------------
# Blocage : 5 échecs => 15 minutes
# ---------------------------------------------------------------------------
def test_blocage_apres_5_echecs(client, registered):
    email, password = registered
    for _ in range(4):
        assert login(client, email, "mauvais").status_code == 401
    r = login(client, email, "mauvais")
    assert r.status_code == 429
    assert "15 minutes" in r.json()["detail"]
    assert 14 * 60 < int(r.headers["retry-after"]) <= 15 * 60

    # Pendant le blocage, même le bon mot de passe est refusé
    assert login(client, email, password).status_code == 429

    # Fin du blocage : la connexion fonctionne et le compteur repart de zéro
    with pool_app.connection() as conn:
        conn.execute("UPDATE app.users SET locked_until = now() - interval '1 second' WHERE email = %s", (email,))
    assert login(client, email, password).status_code == 204
    with pool_app.connection() as conn:
        assert conn.execute("SELECT failed_logins, locked_until FROM app.users WHERE email = %s",
                            (email,)).fetchone() == (0, None)


def test_succes_remet_le_compteur_a_zero(client, registered):
    email, password = registered
    for _ in range(4):
        login(client, email, "mauvais")
    assert login(client, email, password).status_code == 204
    # 4 nouveaux échecs ne bloquent pas : le compteur était revenu à 0
    for _ in range(4):
        assert login(client, email, "mauvais").status_code == 401
