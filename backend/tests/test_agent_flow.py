"""
Parcours de l'écran Question avec un faux modèle (aucun appel réseau, aucun quota consommé) :
question -> outils -> SQL proposé (non exécuté) -> validation -> résultats (fiche, Q4 et Q10).
"""
import json

import pytest

from app.agent.llm import LLMUnavailable, get_llm_client
from app.db.connection import pool_app
from app.main import app
from tests.conftest import TEST_PASSWORD, unique_email

pytestmark = pytest.mark.integration

SQL_BORDEAUX = ("SELECT nom_commune, nb_ventes, prix_m2_moyen FROM v_prix_m2_commune_mat "
                "WHERE code_commune = '33063' AND annee = 2025")


def call(name, **args):
    return {"id": f"call_{name}", "name": name, "arguments": json.dumps(args)}


class FakeLLM:
    """Rejoue une suite de réponses du modèle et garde les messages reçus."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.received = []

    def complete(self, messages, tools):
        self.received.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"content": reply.get("content"), "tool_calls": reply.get("tool_calls", []), "usage": 100}


@pytest.fixture
def use_llm():
    def install(fake):
        app.dependency_overrides[get_llm_client] = lambda: fake
        return fake
    yield install
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def user(new_client):
    c = new_client()
    email = unique_email()
    c.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD})
    assert c.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD}).status_code == 204
    return c


def history_count(client):
    return len(client.get("/api/history").json())


def test_question_puis_validation_et_execution(user, use_llm):
    fake = use_llm(FakeLLM(
        {"tool_calls": [call("chercher_commune", nom="Bordeaux")]},
        {"tool_calls": [call("repondre", explication="Prix moyen au m² des appartements.",
                             sql_propose=SQL_BORDEAUX, recommandations=[])]},
    ))
    r = user.post("/api/agent/questions", json={"question": "Prix moyen au m² à Bordeaux en 2025 ?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sql_propose"] == SQL_BORDEAUX
    assert body["etapes"] == ["chercher_commune", "repondre"]
    # Le résultat de l'outil a bien été renvoyé au modèle
    tool_msgs = [m for m in fake.received[1] if m["role"] == "tool"]
    assert "33063" in tool_msgs[0]["content"]

    # Rien n'a été exécuté avant la validation ; l'utilisateur valide :
    r = user.post(f"/api/agent/questions/{body['history_id']}/execution")
    assert r.status_code == 200
    assert r.json()["lignes"] == [["Bordeaux", 1262, 4480]]

    plan = user.get(f"/api/agent/questions/{body['history_id']}/plan").json()
    assert plan["analyze"] is False and "Scan" in plan["plan"]

    item = user.get(f"/api/history/{body['history_id']}").json()
    assert item["question"] == "Prix moyen au m² à Bordeaux en 2025 ?" and item["sql_propose"] == SQL_BORDEAUX


def test_sql_refuse_renvoye_au_modele_qui_corrige(user, use_llm):
    fake = use_llm(FakeLLM(
        {"tool_calls": [call("repondre", explication="x", sql_propose="DELETE FROM immo.insee_communes")]},
        {"tool_calls": [call("repondre", explication="Corrigé.", sql_propose=SQL_BORDEAUX)]},
    ))
    r = user.post("/api/agent/questions", json={"question": "Supprime les communes"})
    assert r.status_code == 200
    assert r.json()["sql_propose"] == SQL_BORDEAUX
    assert "sql_refuse" in r.json()["etapes"]
    refus = [m for m in fake.received[1] if m["role"] == "tool"][-1]["content"]
    assert refus.startswith("ERREUR : requête refusée")


def test_colonne_inventee_detectee_par_explain(user, use_llm):
    use_llm(FakeLLM(
        {"tool_calls": [call("repondre", explication="x", sql_propose="SELECT prix FROM v_prix_m2_commune_mat")]},
        {"tool_calls": [call("repondre", explication="Corrigé.", sql_propose=SQL_BORDEAUX)]},
    ))
    r = user.post("/api/agent/questions", json={"question": "Prix ?"})
    assert r.status_code == 200 and "sql_refuse" in r.json()["etapes"]


def test_recommandations_conservees_sans_sql(user, use_llm):
    use_llm(FakeLLM(
        {"tool_calls": [call("requetes_couteuses", limite=3)]},
        {"tool_calls": [call("repondre", explication="La vue recalcule son agrégat.",
                             recommandations=["Interroger v_prix_m2_commune_mat"])]},
    ))
    r = user.post("/api/agent/questions", json={"question": "Quelles sont les requêtes les plus lentes ?"})
    body = r.json()
    assert body["sql_propose"] is None and body["recommandations"] == ["Interroger v_prix_m2_commune_mat"]
    # Pas de requête : rien à exécuter
    assert user.post(f"/api/agent/questions/{body['history_id']}/execution").status_code == 422


def test_modele_indisponible_rien_n_est_enregistre(user, use_llm):
    use_llm(FakeLLM(LLMUnavailable("Le service d'analyse est momentanément saturé : réessayez dans 7 s.", 7)))
    before = history_count(user)
    r = user.post("/api/agent/questions", json={"question": "Prix à Lyon ?"})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "7"
    assert "saturé" in r.json()["detail"]
    assert history_count(user) == before


def test_trop_d_etapes(user, use_llm):
    use_llm(FakeLLM(*[{"tool_calls": [call("lire_schema")]}] * 6))
    before = history_count(user)
    r = user.post("/api/agent/questions", json={"question": "Boucle"})
    assert r.status_code == 502 and history_count(user) == before


def test_historique_de_la_conversation_envoye_en_contexte(user, use_llm):
    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="Bordeaux.", sql_propose=SQL_BORDEAUX)]}))
    conversation_id = user.post("/api/agent/questions",
                                json={"question": "Prix au m² à Bordeaux ?"}).json()["conversation_id"]
    fake = use_llm(FakeLLM({"tool_calls": [call("repondre", explication="Toulouse.")]}))
    user.post("/api/agent/questions", json={"question": "et Toulouse ?", "conversation_id": conversation_id})
    contents = [m.get("content") for m in fake.received[0]]
    assert "Prix au m² à Bordeaux ?" in contents and contents[-1] == "et Toulouse ?"
    # La réponse passée est rejouée comme un appel à repondre, suivi de son résultat d'outil
    past = [m for m in fake.received[0] if m["role"] == "assistant"][-1]
    assert past["tool_calls"][0]["function"]["name"] == "repondre"
    assert "33063" in past["tool_calls"][0]["function"]["arguments"]


def test_isolation_entre_utilisateurs(user, new_client, use_llm):
    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="A.", sql_propose=SQL_BORDEAUX)]}))
    history_id = user.post("/api/agent/questions", json={"question": "Question privée de A"}).json()["history_id"]

    other = new_client()
    email = unique_email()
    other.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD})
    other.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    # B ne peut ni exécuter la requête de A, ni voir son plan
    assert other.post(f"/api/agent/questions/{history_id}/execution").status_code == 404
    assert other.get(f"/api/agent/questions/{history_id}/plan").status_code == 404
    # … et l'historique de A n'est jamais envoyé au modèle pour B
    fake = use_llm(FakeLLM({"tool_calls": [call("repondre", explication="B.")]}))
    other.post("/api/agent/questions", json={"question": "Question de B"})
    assert "Question privée de A" not in json.dumps(fake.received[0], ensure_ascii=False)


def test_question_sans_session(client):
    assert client.post("/api/agent/questions", json={"question": "Prix ?"}).status_code == 401


def test_sql_modifie_en_base_refuse_a_l_execution(user, use_llm):
    """Défense en profondeur : même si l'historique contenait un SQL dangereux, il serait revérifié."""
    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="ok", sql_propose=SQL_BORDEAUX)]}))
    history_id = user.post("/api/agent/questions", json={"question": "Prix ?"}).json()["history_id"]
    with pool_app.connection() as conn:
        conn.execute("UPDATE app.historique SET sql_propose = 'DELETE FROM immo.insee_communes' WHERE id = %s",
                     (history_id,))
    r = user.post(f"/api/agent/questions/{history_id}/execution")
    assert r.status_code == 422 and "SELECT" in r.json()["detail"]


TEXTE_TOULOUSE = (
    "**Explication**\nLe prix de Toulouse est dans la vue.\n\n**SQL proposé** :\n\n```sql\n"
    "SELECT prix_m2_moyen FROM immo.v_prix_m2_commune_mat\n"
    "WHERE code_commune = '31555' AND annee = 2025;\n```\n\nRequête rapide."
)


def test_reponse_en_texte_avec_bloc_sql(user, use_llm):
    """gpt-oss rédige parfois sa réponse en Markdown : le bloc ```sql est extrait puis vérifié."""
    use_llm(FakeLLM({"content": TEXTE_TOULOUSE}))
    r = user.post("/api/agent/questions", json={"question": "et à Toulouse ?"})
    body = r.json()
    assert r.status_code == 200 and body["etapes"] == ["texte"]
    assert body["sql_propose"].startswith("SELECT prix_m2_moyen") and not body["sql_propose"].endswith(";")
    assert "```" not in body["explication"] and "Requête rapide." in body["explication"]
    assert not body["explication"].startswith("**")
    assert user.post(f"/api/agent/questions/{body['history_id']}/execution").json()["lignes"] == [[4153]]


def test_bloc_sql_dangereux_en_texte_refuse(user, use_llm):
    fake = use_llm(FakeLLM(
        {"content": "Voici :\n```sql\nDELETE FROM immo.insee_communes;\n```"},
        {"tool_calls": [call("repondre", explication="Corrigé.", sql_propose=SQL_BORDEAUX)]},
    ))
    r = user.post("/api/agent/questions", json={"question": "Nettoie la table"})
    assert r.status_code == 200 and r.json()["sql_propose"] == SQL_BORDEAUX
    assert r.json()["etapes"][0] == "sql_refuse"
    assert fake.received[1][-1]["content"].startswith("Requête refusée")


def test_reponse_en_texte_sans_sql_acceptee(user, use_llm):
    use_llm(FakeLLM({"content": "Les données ne couvrent que 2025 : impossible de comparer avec 2024."}))
    r = user.post("/api/agent/questions", json={"question": "Évolution des prix depuis 2024 ?"})
    assert r.status_code == 200 and r.json()["sql_propose"] is None and r.json()["etapes"] == ["texte"]




def test_diagnostic_et_temps_dans_la_reponse(user, use_llm):
    """Fiche 5.1 (diagnostic si la requête est lente) et Q13 (temps du modèle séparé de la base)."""
    slow = "SELECT nom_commune, prix_m2_moyen FROM immo.v_prix_m2_commune WHERE code_commune = '33063'"
    use_llm(FakeLLM({"tool_calls": [call("chercher_commune", nom="Bordeaux")]},
                    {"tool_calls": [call("repondre", explication="Vue d'origine.", sql_propose=slow)]}))
    body = user.post("/api/agent/questions", json={"question": "Prix à Bordeaux (vue d'origine) ?"}).json()
    assert "v_prix_m2_commune_mat" in body["diagnostic_performance"]
    assert body["duree_modele_ms"] >= 0 and body["duree_base_ms"] > 0

    plan = user.get(f"/api/agent/questions/{body['history_id']}/plan").json()
    assert "v_prix_m2_commune_mat" in plan["diagnostic_performance"]

    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="Vue matérialisée.", sql_propose=SQL_BORDEAUX)]}))
    fast = user.post("/api/agent/questions", json={"question": "Prix à Bordeaux ?"}).json()
    assert fast["diagnostic_performance"] is None


def test_plan_analyze_sur_demande(user, use_llm):
    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="ok", sql_propose=SQL_BORDEAUX)]}))
    history_id = user.post("/api/agent/questions", json={"question": "Prix ?"}).json()["history_id"]
    plan = user.get(f"/api/agent/questions/{history_id}/plan", params={"analyze": "true"}).json()
    assert plan["analyze"] is True and "actual time" in plan["plan"]


def test_reponse_json_ecrite_en_texte(user, use_llm):
    """gpt-oss écrit parfois les arguments de repondre en JSON dans le texte : lus comme un appel."""
    texte = json.dumps({"explication": "Les données ne couvrent que 2025.", "sql_propose": SQL_BORDEAUX,
                        "recommandations": ["Charger d'autres années DVF"]}, ensure_ascii=False)
    use_llm(FakeLLM({"content": texte}))
    body = user.post("/api/agent/questions", json={"question": "Évolution depuis 2020 ?"}).json()
    assert body["explication"] == "Les données ne couvrent que 2025."
    assert body["sql_propose"] == SQL_BORDEAUX and body["recommandations"] == ["Charger d'autres années DVF"]
    assert body["etapes"] == ["texte_json", "repondre"]


def test_reponse_json_avec_sql_dangereux_refusee(user, use_llm):
    texte = json.dumps({"explication": "x", "sql_propose": "DROP TABLE immo.dvf_mutations"})
    use_llm(FakeLLM({"content": texte},
                    {"tool_calls": [call("repondre", explication="Corrigé.", sql_propose=SQL_BORDEAUX)]}))
    r = user.post("/api/agent/questions", json={"question": "Supprime la table"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "sql_refuse" in body["etapes"] and body["sql_propose"] == SQL_BORDEAUX
