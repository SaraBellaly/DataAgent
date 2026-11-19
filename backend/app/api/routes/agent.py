"""
Écran Question (fiche, 5.1) : question -> SQL proposé -> validation -> résultats, plan, recommandations.

- POST /api/agent/questions                  : l'agent propose (rien n'est exécuté) ;
- POST /api/agent/questions/{id}/execution   : l'utilisateur valide ; exécution sous analyst_ro ;
- GET  /api/agent/questions/{id}/plan        : plan EXPLAIN (ANALYZE seulement sur demande).

L'échange est toujours relu dans l'historique de l'utilisateur de la session : on ne peut
valider que SA requête, et jamais un SQL envoyé directement par le navigateur.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import repositories as repo
from app.agent import orchestrator, tools
from app.agent.llm import ChatClient, LLMUnavailable, get_llm_client
from app.agent.sql_guard import SqlRejected
from app.api.deps import get_current_user
from app.core.config import settings
from app.db.connection import pool_app
from app.schemas import AgentAnswerOut, ExecutionResult, Message, PlanOut, QuestionRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])

ERRORS = {401: {"model": Message}, 404: {"model": Message}, 422: {"model": Message},
          502: {"model": Message}, 503: {"model": Message}}


@router.post("/questions", response_model=AgentAnswerOut, responses=ERRORS)
def ask_question(body: QuestionRequest, user: dict = Depends(get_current_user),
                 llm: ChatClient = Depends(get_llm_client)):
    try:
        answer = orchestrator.ask(user["id"], body.question, llm)
    except LLMUnavailable as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e), headers=headers) from None
    except orchestrator.AgentFailed as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from None
    return AgentAnswerOut(history_id=answer.history_id, question=answer.question,
                          sql_propose=answer.sql_propose, explication=answer.explication,
                          recommandations=answer.recommandations, etapes=answer.etapes,
                          diagnostic_performance=answer.diagnostic_performance,
                          duree_modele_ms=answer.duree_modele_ms, duree_base_ms=answer.duree_base_ms)


def _own_sql(user_id: int, history_id: int) -> str:
    with pool_app.connection() as conn:
        item = repo.get_history_item(conn, user_id, history_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Introuvable.")
    if not item["sql_propose"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cet échange ne contient aucune requête à exécuter.")
    return item["sql_propose"]


@router.post("/questions/{history_id}/execution", response_model=ExecutionResult, responses=ERRORS)
def execute_validated(history_id: int, user: dict = Depends(get_current_user)):
    """Exécution après validation explicite de l'utilisateur (bouton « Valider et exécuter »)."""
    sql = _own_sql(user["id"], history_id)
    try:
        return tools.execute_select(sql, max_rows=settings.agent_max_result_rows)
    except (SqlRejected, tools.ToolError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None


@router.get("/questions/{history_id}/plan", response_model=PlanOut, responses=ERRORS)
def query_plan(history_id: int, analyze: bool = Query(False, description="EXPLAIN ANALYZE : exécute la requête"),
               user: dict = Depends(get_current_user)):
    sql = _own_sql(user["id"], history_id)
    try:
        plan = tools.explain_select(sql, analyze=analyze)
        return PlanOut(analyze=analyze, plan=plan, diagnostic_performance=tools.performance_diagnosis(sql, plan))
    except (SqlRejected, tools.ToolError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
