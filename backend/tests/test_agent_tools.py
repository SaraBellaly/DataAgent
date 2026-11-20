"""
Outils de l'agent sur la base réelle, avec analyst_ro (fiche, Q5 et Q14).
"""
import pytest

from app.agent import tools
from app.agent.sql_guard import SqlRejected

pytestmark = pytest.mark.integration


def test_schema_liste_les_tables_et_la_vue_materialisee(_app_started):
    schema = tools.read_schema()
    for rel in ("dvf_mutations", "insee_communes", "v_prix_m2_commune", "v_prix_m2_commune_mat"):
        assert f"immo.{rel}" in schema
    # Colonnes d'une vue matérialisée : absentes d'information_schema, lues dans pg_catalog
    assert "- prix_m2_moyen integer" in schema
    assert "dvf_mutations.dvf_mutations_code_commune_idx" in schema  # index existants
    assert "lot1_numero … lot5_numero" in schema
    assert tools.allowed_relations() == {"dvf_mutations", "insee_communes", "v_prix_m2_commune",
                                         "v_prix_m2_commune_mat"}


@pytest.mark.parametrize("nom, code", [("Bordeaux", "33063"), ("toulouse", "31555"),
                                       ("saint-etienne", "42218"), ("Paris 6e", "75106")])
def test_chercher_commune(_app_started, nom, code):
    assert tools.find_commune(nom)[0]["code_insee"] == code


def test_requetes_couteuses(_app_started):
    rows = tools.costly_queries(limite=5)
    assert 0 < len(rows) <= 5
    assert {"requete", "appels", "temps_total_ms", "temps_moyen_ms"} <= rows[0].keys()
    totals = [r["temps_total_ms"] for r in rows]
    assert totals == sorted(totals, reverse=True)


def test_explain_sans_execution(_app_started):
    plan = tools.explain_select("SELECT * FROM immo.v_prix_m2_commune_mat WHERE code_commune = '33063'")
    assert "Index Scan" in plan or "Bitmap" in plan
    assert "actual time" not in plan  # estimation seule : la requête n'a pas tourné


def test_execution_resultat_de_reference(_app_started):
    r = tools.execute_select("SELECT nom_commune, nb_ventes, prix_m2_moyen FROM v_prix_m2_commune_mat "
                             "WHERE code_commune = '33063' AND annee = 2025")
    assert r["colonnes"] == ["nom_commune", "nb_ventes", "prix_m2_moyen"]
    assert r["lignes"] == [["Bordeaux", 1262, 4480]]


def test_execution_tronquee(_app_started):
    r = tools.execute_select("SELECT code_insee FROM insee_communes", max_rows=10)
    assert r["nb_lignes"] == 10 and r["tronque"] is True


def test_execution_refuse_une_ecriture(_app_started):
    with pytest.raises(SqlRejected):
        tools.execute_select("DELETE FROM immo.insee_communes")


def test_colonne_inventee_renvoie_une_erreur_lisible(_app_started):
    with pytest.raises(tools.ToolError, match="colonne_inventee"):
        tools.explain_select("SELECT colonne_inventee FROM immo.insee_communes")


def test_requete_trop_longue_interrompue(_app_started):
    # Délai réduit pour le test ; en service, la limite est celle du rôle (30 s)
    with pytest.raises(tools.ToolError, match="délai maximal"):
        tools.execute_select("SELECT count(*) FROM immo.v_prix_m2_commune", timeout_ms=50)


def test_requetes_couteuses_ne_montrent_pas_le_schema_app(_app_started, client):
    # Génère des requêtes de l'application (app_agent) dans pg_stat_statements
    client.post("/api/auth/login", json={"email": "pytest-inconnu@example.com", "password": "x"})
    rows = tools.costly_queries(limite=20)
    assert rows and not any("app." in r["requete"] or "password_hash" in r["requete"] for r in rows)


def test_plan_generique_pour_requete_parametree(_app_started):
    """Les requêtes de pg_stat_statements contiennent $1 : EXPLAIN (GENERIC_PLAN), PostgreSQL 16."""
    plan = tools.explain_select("SELECT * FROM immo.dvf_mutations WHERE code_commune = $1")
    assert "dvf_mutations_code_commune_idx" in plan
    with pytest.raises(tools.ToolError, match="paramétrée"):
        tools.explain_select("SELECT * FROM immo.dvf_mutations WHERE code_commune = $1", analyze=True)


@pytest.mark.parametrize("sql, attendu", [
    ("SELECT * FROM immo.v_prix_m2_commune WHERE code_commune = '33063'", "v_prix_m2_commune_mat"),
    ("SELECT count(*) FROM immo.dvf_mutations WHERE date_mutation BETWEEN '2025-06-01' AND '2025-06-30'",
     "lit toute la table dvf_mutations"),
    ("SELECT prix_m2_moyen FROM immo.v_prix_m2_commune_mat WHERE code_commune = '33063'", None),
    ("SELECT count(DISTINCT id_mutation) FROM immo.dvf_mutations WHERE code_commune = '33063'", None),
    ("SELECT * FROM immo.dvf_mutations LIMIT 5", None),   # Seq Scan, mais instantané
])
def test_diagnostic_de_performance(_app_started, sql, attendu):
    diagnosis = tools.performance_diagnosis(sql, tools.explain_select(sql))
    if attendu is None:
        assert diagnosis is None
    else:
        assert diagnosis.startswith("Requête potentiellement lente") and attendu in diagnosis


def test_communes_a_arrondissements_filtre_pret_a_l_emploi(_app_started):
    """Lyon : le modèle de secours avait oublié le 3e arrondissement en recopiant les codes à la main."""
    lyon = tools.find_commune("Lyon")[0]
    assert lyon["code_insee"] == "69123" and lyon["arrondissements"] == 9
    r = tools.execute_select(
        "SELECT round(sum(prix_m2_moyen * nb_ventes)::numeric / sum(nb_ventes), 2) FROM v_prix_m2_commune_mat "
        f"WHERE annee = 2025 AND {lyon['filtre_sql']}")
    assert float(r["lignes"][0][0]) == 4745.61
    assert "arrondissements" not in tools.find_commune("Bordeaux")[0]
    assert tools.find_commune("Paris")[0]["arrondissements"] == 20
    assert tools.find_commune("Marseille")[0]["arrondissements"] == 16
