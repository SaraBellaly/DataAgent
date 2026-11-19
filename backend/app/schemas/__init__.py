"""
Schémas Pydantic : validation des entrées et forme des réponses de l'API.

Minimisation (fiche, Q15) : l'inscription ne demande que l'email et le mot de passe.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Credentials(BaseModel):
    """Corps des requêtes d'inscription et de connexion."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normaliser_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(Credentials):
    # Pas de longueur minimale à la connexion : un mot de passe court est simplement faux
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class DeleteAccountRequest(BaseModel):
    """La suppression exige une confirmation explicite (écran Historique, fiche 5.1)."""

    model_config = ConfigDict(extra="forbid")

    confirmation: bool


class HistoryItem(BaseModel):
    id: int
    question: str
    sql_propose: str | None
    explication: str | None
    recommandations: list[str] = []
    created_at: datetime


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=1000)

    @field_validator("question")
    @classmethod
    def nettoyer(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Question trop courte.")
        return v


class AgentAnswerOut(BaseModel):
    history_id: int
    question: str
    sql_propose: str | None
    explication: str
    recommandations: list[str]
    etapes: list[str]
    diagnostic_performance: str | None = None
    duree_modele_ms: float
    duree_base_ms: float


class ExecutionResult(BaseModel):
    colonnes: list[str]
    lignes: list[list[Any]]
    nb_lignes: int
    tronque: bool
    duree_ms: float


class PlanOut(BaseModel):
    analyze: bool
    plan: str
    diagnostic_performance: str | None = None


class Message(BaseModel):
    detail: str
