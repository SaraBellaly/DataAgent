"""
Conversations (écran Historique) : liste, détail avec résultats déjà obtenus, renommage, suppression.
Chaque utilisateur ne voit que les siennes ; celles d'un autre renvoient « Introuvable. ».
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import repositories as repo
from app.api.deps import get_current_user
from app.db.connection import pool_app
from app.schemas import ConversationDetail, ConversationOut, Message, RenameRequest

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
NOT_FOUND = {401: {"model": Message}, 404: {"model": Message}}


@router.get("", response_model=list[ConversationOut], responses={401: {"model": Message}})
def list_my_conversations(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                          user: dict = Depends(get_current_user)):
    with pool_app.connection() as conn:
        return repo.list_conversations(conn, user["id"], limit, offset)


@router.get("/{conversation_id}", response_model=ConversationDetail, responses=NOT_FOUND)
def get_my_conversation(conversation_id: int, user: dict = Depends(get_current_user)):
    with pool_app.connection() as conn:
        conversation = repo.get_conversation(conn, user["id"], conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
        exchanges = repo.conversation_history(conn, user["id"], conversation_id)
    return {**conversation, "echanges": exchanges}


@router.patch("/{conversation_id}", response_model=ConversationOut, responses=NOT_FOUND)
def rename_my_conversation(conversation_id: int, body: RenameRequest, user: dict = Depends(get_current_user)):
    with pool_app.connection() as conn:
        if not repo.rename_conversation(conn, user["id"], conversation_id, body.titre):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
        conversation = repo.get_conversation(conn, user["id"], conversation_id)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_my_conversation(conversation_id: int, user: dict = Depends(get_current_user)):
    """Supprime la conversation et tous ses échanges (ON DELETE CASCADE)."""
    with pool_app.connection() as conn:
        if not repo.delete_conversation(conn, user["id"], conversation_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
