"""
Tableau de bord : statistiques réelles de l'utilisateur connecté et requêtes les plus coûteuses
de la base (pg_stat_statements, lecture seule, sans les requêtes du schéma app). Aucune donnée inventée.
"""
from fastapi import APIRouter, Depends

from app import repositories as repo
from app.agent import tools
from app.api.deps import get_current_user
from app.db.connection import pool_app
from app.schemas import DashboardOut, Message

router = APIRouter(prefix="/api/dashboard", tags=["tableau de bord"])


@router.get("", response_model=DashboardOut, responses={401: {"model": Message}})
def my_dashboard(user: dict = Depends(get_current_user)):
    with pool_app.connection() as conn:
        stats = repo.user_stats(conn, user["id"])
        recent = repo.list_history(conn, user["id"], 5)
    return {**stats, "dernieres_questions": recent, "requetes_couteuses": tools.costly_queries(limite=5)}
