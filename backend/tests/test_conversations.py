"""
Conversations, résultats conservés, suppression, tableau de bord (écran Historique et Dashboard).
"""
import json

import pytest

from tests.test_agent_flow import SQL_BORDEAUX, FakeLLM, call, use_llm, user  # noqa: F401 (fixtures)
from tests.conftest import TEST_PASSWORD, unique_email

pytestmark = pytest.mark.integration


def answer(sql=SQL_BORDEAUX, text="ok"):
    return {"tool_calls": [call("repondre", explication=text, sql_propose=sql)]}


def ask(client, question, conversation_id=None):
    payload = {"question": question} | ({"conversation_id": conversation_id} if conversation_id else {})
    r = client.post("/api/agent/questions", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_premiere_question_cree_une_conversation_intitulee(user, use_llm):
    use_llm(FakeLLM(answer()))
    body = ask(user, "Prix moyen au m² à Bordeaux en 2025 ?")
    convs = user.get("/api/conversations").json()
    assert convs[0]["id"] == body["conversation_id"]
    assert convs[0]["titre"] == "Prix moyen au m² à Bordeaux en 2025 ?" and convs[0]["nb_echanges"] == 1


def test_contexte_limite_a_la_conversation(user, use_llm):
    use_llm(FakeLLM(answer(text="Bordeaux.")))
    first = ask(user, "Question de la conversation A")
    fake = use_llm(FakeLLM(answer(text="Autre.")))
    second = ask(user, "Question d'une nouvelle conversation")
    assert second["conversation_id"] != first["conversation_id"]
    assert "conversation A" not in json.dumps(fake.received[0], ensure_ascii=False)


def test_detail_conversation_et_resultat_conserve(user, use_llm):
    use_llm(FakeLLM(answer()))
    body = ask(user, "Prix à Bordeaux ?")
    use_llm(FakeLLM(answer(text="Suite.")))
    ask(user, "et la suite ?", body["conversation_id"])
    user.post(f"/api/agent/questions/{body['history_id']}/execution")

    detail = user.get(f"/api/conversations/{body['conversation_id']}").json()
    assert [e["question"] for e in detail["echanges"]] == ["Prix à Bordeaux ?", "et la suite ?"]
    first = detail["echanges"][0]
    # Résultat relu sans réexécuter la requête
    assert first["resultat"]["lignes"] == [["Bordeaux", 1262, 4480]] and first["executed_at"]
    assert detail["echanges"][1]["resultat"] is None


def test_renommer_et_supprimer_une_conversation(user, use_llm):
    use_llm(FakeLLM(answer()))
    body = ask(user, "À supprimer")
    cid = body["conversation_id"]
    r = user.patch(f"/api/conversations/{cid}", json={"titre": "  Prix   Bordeaux "})
    assert r.json()["titre"] == "Prix Bordeaux" and r.json()["nb_echanges"] == 1
    assert user.delete(f"/api/conversations/{cid}").status_code == 204
    assert user.get(f"/api/conversations/{cid}").status_code == 404
    assert user.get(f"/api/history/{body['history_id']}").status_code == 404   # échanges supprimés


def test_supprimer_un_echange(user, use_llm):
    use_llm(FakeLLM(answer()))
    body = ask(user, "Échange à supprimer")
    assert user.delete(f"/api/history/{body['history_id']}").status_code == 204
    assert user.delete(f"/api/history/{body['history_id']}").status_code == 404


def test_conversations_cloisonnees(user, new_client, use_llm):
    use_llm(FakeLLM(answer()))
    cid = ask(user, "Conversation privée de A")["conversation_id"]
    other = new_client()
    email = unique_email()
    other.post("/api/auth/register", json={"email": email, "password": TEST_PASSWORD})
    other.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert other.get(f"/api/conversations/{cid}").status_code == 404
    assert other.delete(f"/api/conversations/{cid}").status_code == 404
    assert other.patch(f"/api/conversations/{cid}", json={"titre": "x"}).status_code == 404
    # B ne peut pas poursuivre la conversation de A
    use_llm(FakeLLM(answer()))
    assert other.post("/api/agent/questions",
                      json={"question": "Suite ?", "conversation_id": cid}).status_code == 404
    assert other.get("/api/conversations").json() == []


def test_tableau_de_bord(user, use_llm):
    empty = user.get("/api/dashboard").json()
    assert empty["nb_questions"] == 0 and empty["derniere_activite"] is None
    use_llm(FakeLLM(answer()))
    body = ask(user, "Prix ?")
    use_llm(FakeLLM({"tool_calls": [call("repondre", explication="x", recommandations=["Index"])]}))
    ask(user, "Optimisation ?", body["conversation_id"])
    user.post(f"/api/agent/questions/{body['history_id']}/execution")
    d = user.get("/api/dashboard").json()
    assert (d["nb_conversations"], d["nb_questions"], d["nb_requetes_proposees"],
            d["nb_requetes_executees"], d["nb_avec_recommandations"]) == (1, 2, 1, 1, 1)
    assert [q["question"] for q in d["dernieres_questions"]] == ["Optimisation ?", "Prix ?"]
    assert d["requetes_couteuses"] and not any("app." in q["requete"] for q in d["requetes_couteuses"])


def test_tableau_de_bord_sans_session(client):
    assert client.get("/api/dashboard").status_code == 401
