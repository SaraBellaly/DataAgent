"""
Mots de passe (argon2id) et jetons de session.

- Le mot de passe n'est jamais stocké ni journalisé : seul son haché argon2id (avec sel) l'est.
- Le jeton de session est un aléa de 256 bits posé dans le cookie ; la base ne garde que son
  empreinte SHA-256, pour qu'une fuite de la table sessions ne donne aucun jeton utilisable.
"""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Paramètres par défaut d'argon2-cffi (argon2id, profil RFC 9106 « low memory »)
_hasher = PasswordHasher()

# Haché d'un mot de passe aléatoire : vérifié quand l'email est inconnu, pour que la réponse
# prenne le même temps qu'avec un compte existant (ne pas révéler l'existence d'un compte).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Vérifie le mot de passe ; password_hash=None simule une vérification (email inconnu)."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True si les paramètres d'argon2 ont changé depuis le hachage."""
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> tuple[str, bytes]:
    """Renvoie (jeton à poser dans le cookie, empreinte SHA-256 à stocker en base)."""
    token = secrets.token_urlsafe(32)
    return token, token_digest(token)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
