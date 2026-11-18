"""
Routes de l'historique des conversations utilisateur.

Phase 3.1 : Ce fichier est préparé pour la Phase 3.3.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/history", tags=["history"])

# TODO Phase 3.3:
# - GET /history : liste des conversations
# - GET /history/{id} : détails d'une conversation
# - DELETE /history/{id} : supprimer une conversation
# - DELETE /history : supprimer tout l'historique
