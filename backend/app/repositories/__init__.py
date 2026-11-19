"""
Accès aux tables du schéma app, avec le rôle app_agent.

Toutes les valeurs sont passées en paramètres psycopg (%s), jamais concaténées au SQL.
Chaque fonction reçoit la connexion : la transaction est gérée par l'appelant (services).
Toute lecture ou écriture de l'historique filtre sur l'identifiant tiré de la session.
"""
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


# ---------------------------------------------------------------------------
# Comptes
# ---------------------------------------------------------------------------
def create_user(conn: Connection, email: str, password_hash: str) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO app.users (email, password_hash) VALUES (%s, %s) "
            "RETURNING id, email, created_at",
            (email, password_hash),
        )
        return cur.fetchone()


def get_user_for_login(conn: Connection, email: str) -> dict[str, Any] | None:
    """Verrouille la ligne (FOR UPDATE) : deux connexions simultanées comptent bien deux échecs."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, password_hash, failed_logins, locked_until, "
            "       greatest(0, ceil(extract(epoch FROM locked_until - now())))::int AS lock_seconds_left "
            "FROM app.users WHERE email = %s FOR UPDATE",
            (email,),
        )
        return cur.fetchone()


def record_failed_login(conn: Connection, user_id: int, max_failed: int, lockout_minutes: int) -> int | None:
    """Compte un échec ; au max_failed-ième, bloque le compte. Renvoie les secondes de blocage, ou None."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE app.users SET "
            "  failed_logins = CASE WHEN failed_logins + 1 >= %(max)s THEN 0 ELSE failed_logins + 1 END, "
            "  locked_until  = CASE WHEN failed_logins + 1 >= %(max)s "
            "                       THEN now() + make_interval(mins => %(mins)s) ELSE NULL END "
            "WHERE id = %(id)s "
            "RETURNING ceil(extract(epoch FROM locked_until - now()))::int",
            {"id": user_id, "max": max_failed, "mins": lockout_minutes},
        )
        (seconds,) = cur.fetchone()
        return seconds


def record_successful_login(conn: Connection, user_id: int, new_hash: str | None = None) -> None:
    conn.execute(
        "UPDATE app.users SET failed_logins = 0, locked_until = NULL, "
        "password_hash = coalesce(%s, password_hash) WHERE id = %s",
        (new_hash, user_id),
    )


def delete_user(conn: Connection, user_id: int) -> None:
    """ON DELETE CASCADE supprime aussi ses sessions et tout son historique."""
    conn.execute("DELETE FROM app.users WHERE id = %s", (user_id,))


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def create_session(conn: Connection, user_id: int, token_hash: bytes, duration_hours: int) -> None:
    conn.execute(
        "INSERT INTO app.sessions (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, now() + make_interval(hours => %s))",
        (user_id, token_hash, duration_hours),
    )


def purge_dead_sessions(conn: Connection, user_id: int) -> None:
    """Supprime les sessions expirées ou révoquées de l'utilisateur (ménage à la connexion)."""
    conn.execute(
        "DELETE FROM app.sessions WHERE user_id = %s AND (expires_at <= now() OR revoked_at IS NOT NULL)",
        (user_id,),
    )


def get_user_by_session(conn: Connection, token_hash: bytes) -> dict[str, Any] | None:
    """Utilisateur d'une session valide : non révoquée et non expirée (vérifié côté serveur)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT u.id, u.email, u.created_at "
            "FROM app.sessions s JOIN app.users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()",
            (token_hash,),
        )
        return cur.fetchone()


def revoke_session(conn: Connection, token_hash: bytes) -> None:
    conn.execute(
        "UPDATE app.sessions SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
        (token_hash,),
    )


# ---------------------------------------------------------------------------
# Historique (toujours filtré sur user_id)
# ---------------------------------------------------------------------------
def add_history(conn: Connection, user_id: int, question: str,
                sql_propose: str | None, explication: str | None) -> int:
    (history_id,) = conn.execute(
        "INSERT INTO app.historique (user_id, question, sql_propose, explication) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, question, sql_propose, explication),
    ).fetchone()
    return history_id


def list_history(conn: Connection, user_id: int, limit: int, offset: int = 0) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, question, sql_propose, explication, created_at FROM app.historique "
            "WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
        return cur.fetchall()


def get_history_item(conn: Connection, user_id: int, history_id: int) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, question, sql_propose, explication, created_at FROM app.historique "
            "WHERE id = %s AND user_id = %s",
            (history_id, user_id),
        )
        return cur.fetchone()
