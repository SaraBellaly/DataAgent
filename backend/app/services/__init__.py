"""
Logique d'authentification : inscription, connexion avec blocage, déconnexion, suppression.

Chaque fonction ouvre une connexion app_agent et une transaction (commit à la sortie du bloc
`with`, rollback en cas d'exception).
"""
from dataclasses import dataclass

from psycopg import errors

from app import repositories as repo
from app.core.config import settings
from app.core.security import hash_password, needs_rehash, new_session_token, token_digest, verify_password
from app.db.connection import pool_app


class EmailAlreadyUsed(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass
class AccountLocked(Exception):
    seconds_left: int


def register(email: str, password: str) -> dict:
    password_hash = hash_password(password)  # hors transaction : argon2 est volontairement lent
    try:
        with pool_app.connection() as conn:
            return repo.create_user(conn, email, password_hash)
    except errors.UniqueViolation:
        raise EmailAlreadyUsed from None


def login(email: str, password: str) -> str:
    """Renvoie le jeton de session à poser dans le cookie.

    Lève InvalidCredentials (message unique, que l'email existe ou non) ou AccountLocked.
    """
    with pool_app.connection() as conn:
        user = repo.get_user_for_login(conn, email)
        if user is None:
            verify_password(None, password)  # même durée qu'avec un compte existant
            raise InvalidCredentials
        if user["lock_seconds_left"] > 0:
            raise AccountLocked(user["lock_seconds_left"])

        if not verify_password(user["password_hash"], password):
            seconds = repo.record_failed_login(
                conn, user["id"], settings.max_failed_logins, settings.lockout_minutes
            )
            conn.commit()  # l'échec doit être compté même si l'on lève une exception
            if seconds:
                raise AccountLocked(seconds)
            raise InvalidCredentials

        new_hash = hash_password(password) if needs_rehash(user["password_hash"]) else None
        repo.record_successful_login(conn, user["id"], new_hash)
        repo.purge_dead_sessions(conn, user["id"])
        token, digest = new_session_token()
        repo.create_session(conn, user["id"], digest, settings.session_duration_hours)
        return token


def user_from_token(token: str) -> dict | None:
    with pool_app.connection() as conn:
        return repo.get_user_by_session(conn, token_digest(token))


def logout(token: str) -> None:
    with pool_app.connection() as conn:
        repo.revoke_session(conn, token_digest(token))


def delete_account(user_id: int) -> None:
    with pool_app.connection() as conn:
        repo.delete_user(conn, user_id)
