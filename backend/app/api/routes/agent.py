"""
Routes de l'agent IA Text-to-SQL : génération et exécution de requêtes.

Phase 3.1 : Ce fichier est préparé pour la Phase 3.4.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])

# TODO Phase 3.4:
# - POST /agent/query : traduire question en SQL
# - POST /agent/execute : exécuter une requête SQL (validation stricte)
# - POST /agent/explain : expliquer un plan d'exécution
# - POST /agent/recommend : recommander des optimisations
