"""
Vérification du SQL généré (fiche, Q10 : « une seule instruction, de type SELECT »).
Tests unitaires : aucune base nécessaire.
"""
import pytest

from app.agent.sql_guard import SqlRejected, check_select

ALLOWED = frozenset({"dvf_mutations", "insee_communes", "v_prix_m2_commune", "v_prix_m2_commune_mat"})


@pytest.mark.parametrize("sql", [
    "SELECT nom_commune, nb_ventes, prix_m2_moyen FROM v_prix_m2_commune_mat "
    "WHERE code_commune = '33063' AND annee = 2025",
    "select * from immo.insee_communes limit 5;",                       # point-virgule final, schéma explicite
    "SELECT 1 /* ; DROP TABLE immo.dvf_mutations */",                    # le « ; » est dans un commentaire
    "SELECT ';DELETE FROM x' AS texte",                                  # … ou dans une chaîne
    "WITH v AS (SELECT code_commune, count(*) n FROM dvf_mutations GROUP BY 1) "
    "SELECT v.*, c.libelle FROM v LEFT JOIN insee_communes c ON c.code_insee = v.code_commune "
    "ORDER BY n DESC LIMIT 10",
    "SELECT code_commune FROM v_prix_m2_commune_mat UNION SELECT code_insee FROM insee_communes",
    "SELECT count(DISTINCT id_mutation) FROM dvf_mutations WHERE date_mutation BETWEEN '2025-06-01' AND '2025-06-30'",
    "SELECT * FROM (SELECT code_insee, pmun FROM insee_communes WHERE pmun > 100000) t ORDER BY pmun DESC",
])
def test_select_accepte(sql):
    assert check_select(sql, ALLOWED).sql == sql.strip().rstrip(";").strip()


@pytest.mark.parametrize("sql, motif", [
    ("", "vide"),
    ("   ", "vide"),
    ("SELECT 1; SELECT 2", "Une seule instruction"),
    ("SELECT 1; DROP TABLE immo.insee_communes", "Une seule instruction"),
    ("SELECT 1 -- commentaire\n; DELETE FROM immo.insee_communes", "Une seule instruction"),
    ("INSERT INTO immo.insee_communes (code_insee) VALUES ('x')", "SELECT"),
    ("UPDATE immo.dvf_mutations SET valeur_fonciere = 0", "SELECT"),
    ("DELETE FROM immo.insee_communes", "SELECT"),
    ("DROP TABLE immo.dvf_mutations", "SELECT"),
    ("CREATE INDEX i ON immo.dvf_mutations (date_mutation)", "SELECT"),
    ("ALTER TABLE immo.insee_communes ADD COLUMN x int", "SELECT"),
    ("TRUNCATE immo.insee_communes", "SELECT"),
    ("COPY immo.insee_communes TO '/tmp/x.csv'", ""),
    ("WITH d AS (DELETE FROM immo.insee_communes RETURNING *) SELECT * FROM d", ""),
    ("SELECT * INTO immo.copie FROM immo.insee_communes", "INTO"),
    ("SELECT * FROM immo.insee_communes FOR UPDATE", "LOCK"),
    ("SELECT pg_sleep(60)", "pg_sleep"),
    ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
    ("SELECT set_config('default_transaction_read_only', 'off', false)", "set_config"),
    ("SELECT query_to_xml('select * from app.users', true, true, '')", "query_to_xml"),
    ("SELECT * FROM dblink('host=x', 'select 1') AS t(x int)", ""),
    ("SELECT email, password_hash FROM app.users", "schéma immo"),
    ("SELECT * FROM pg_catalog.pg_authid", "schéma immo"),
    ("SELECT * FROM utilisateurs", "Relation inconnue"),
    ("SELECT * FROM autrebase.immo.dvf_mutations", ""),
    ("EXPLAIN ANALYZE DELETE FROM immo.insee_communes", ""),
    ("DO $$ BEGIN DELETE FROM immo.insee_communes; END $$", ""),
    ("SET ROLE immo_admin", ""),
    ("CALL une_procedure()", ""),
    ("VACUUM immo.dvf_mutations", ""),
])
def test_requete_refusee(sql, motif):
    with pytest.raises(SqlRejected) as exc:
        check_select(sql, ALLOWED)
    assert motif in str(exc.value)


def test_requete_trop_longue():
    with pytest.raises(SqlRejected, match="trop longue"):
        check_select("SELECT 1 " + " " * 10_001, ALLOWED)
