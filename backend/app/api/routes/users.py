"""
Compte de l'utilisateur connecté : consultation et suppression (fiche, écran 4).
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app import services
from app.api.deps import clear_session_cookie, get_current_user
from app.schemas import DeleteAccountRequest, Message, UserOut

router = APIRouter(prefix="/api/users", tags=["compte"])


@router.get("/me", response_model=UserOut, responses={401: {"model": Message}})
def me(user: dict = Depends(get_current_user)):
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT,
               responses={400: {"model": Message}, 401: {"model": Message}})
def delete_me(body: DeleteAccountRequest, response: Response, user: dict = Depends(get_current_user)):
    """Supprime le compte, toutes ses sessions et tout son historique, après confirmation."""
    if not body.confirmation:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Suppression non confirmée : rien n'a été modifié.")
    services.delete_account(user["id"])
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
