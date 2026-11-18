"""
Routes de gestion des utilisateurs : profil, liste, suppression.

Phase 3.1 : Ce fichier est préparé pour la Phase 3.2.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

# TODO Phase 3.2:
# - GET /users/me : profil utilisateur courant
# - PUT /users/me : modifier profil
# - DELETE /users/me : supprimer compte
# - GET /users : liste utilisateurs (admin)
