"""
Routes d'authentification : inscription, connexion, refresh token.

Phase 3.1 : Ce fichier est préparé pour la Phase 3.2.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["authentication"])

# TODO Phase 3.2:
# - POST /auth/register : inscription
# - POST /auth/login : connexion (retourne JWT)
# - POST /auth/refresh : rafraîchir le token
# - POST /auth/logout : déconnexion
