"""
Dépendances FastAPI : utilisateur courant tiré du cookie de session.

L'identifiant de l'utilisateur vient toujours de la session côté serveur, jamais d'un
paramètre envoyé par le navigateur (fiche, Q10 et Q15).
"""
from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.services import user_from_token

NOT_AUTHENTICATED = "Session absente ou expirée : veuillez vous reconnecter."


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_duration_hours * 3600,
        httponly=True,       # illisible par JavaScript
        samesite="strict",   # jamais envoyé par une requête venant d'un autre site (CSRF)
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name, path="/", httponly=True,
        samesite="strict", secure=settings.cookie_secure,
    )


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def get_current_user(request: Request) -> dict:
    token = get_session_token(request)
    user = user_from_token(token) if token else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=NOT_AUTHENTICATED)
    return user
