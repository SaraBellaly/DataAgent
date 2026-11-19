"""
Inscription, connexion et déconnexion (fiche de cadrage, écrans 1 et 2).
"""
import math

from fastapi import APIRouter, HTTPException, Request, Response, status

from app import services
from app.api.deps import clear_session_cookie, get_session_token, set_session_cookie
from app.schemas import Credentials, LoginRequest, Message, UserOut

router = APIRouter(prefix="/api/auth", tags=["authentification"])

INVALID_CREDENTIALS = "Email ou mot de passe incorrect."


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut,
             responses={409: {"model": Message}})
def register(body: Credentials):
    """Crée le compte (mot de passe haché argon2id). N'ouvre pas de session :
    l'interface redirige ensuite vers l'écran de connexion."""
    try:
        return services.register(body.email, body.password)
    except services.EmailAlreadyUsed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette adresse email est déjà utilisée.") from None


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT,
             responses={401: {"model": Message}, 429: {"model": Message}})
def login(body: LoginRequest, response: Response):
    """Ouvre une session de 8 heures et pose le cookie HttpOnly + SameSite.

    Message d'erreur unique : il ne dit pas si c'est l'email ou le mot de passe qui est faux.
    Après 5 échecs, le compte est bloqué 15 minutes (429, avec le délai restant)."""
    try:
        token = services.login(body.email, body.password)
    except services.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS) from None
    except services.AccountLocked as exc:
        minutes = max(1, math.ceil(exc.seconds_left / 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop d'échecs de connexion : réessayez dans {minutes} minute{'s' if minutes > 1 else ''}.",
            headers={"Retry-After": str(exc.seconds_left)},
        ) from None
    set_session_cookie(response, token)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response):
    """Invalide la session côté serveur et efface le cookie (sans erreur si déjà déconnecté)."""
    token = get_session_token(request)
    if token:
        services.logout(token)
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
