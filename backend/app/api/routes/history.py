"""
Historique personnel (fiche, écran 4) : chacun ne voit que ses propres échanges.

Les échanges sont enregistrés par l'agent (repositories.add_history), pas par cette route.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import repositories as repo
from app.api.deps import get_current_user
from app.db.connection import pool_app
from app.schemas import HistoryItem, Message

router = APIRouter(prefix="/api/history", tags=["historique"])


@router.get("", response_model=list[HistoryItem], responses={401: {"model": Message}})
def list_my_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    with pool_app.connection() as conn:
        return repo.list_history(conn, user["id"], limit, offset)


@router.get("/{history_id}", response_model=HistoryItem,
            responses={401: {"model": Message}, 404: {"model": Message}})
def get_my_history_item(history_id: int, user: dict = Depends(get_current_user)):
    """« Introuvable » aussi pour l'échange d'un autre utilisateur : son existence n'est pas révélée."""
    with pool_app.connection() as conn:
        item = repo.get_history_item(conn, user["id"], history_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
    return item


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses={401: {"model": Message}, 404: {"model": Message}})
def delete_my_history_item(history_id: int, user: dict = Depends(get_current_user)):
    with pool_app.connection() as conn:
        if not repo.delete_history_item(conn, user["id"], history_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
