-- Vue alternative : v_prix_m2_commune_large
-- Ignore les dépendances (caves, parkings) dans le comptage des locaux
-- pour augmenter la couverture des ventes d'appartements.
--
-- Différences avec v_prix_m2_commune (vue stricte) :
--   Vue stricte : UN SEUL local de type Appartement (81 133 ventes en 2025, 20%)
--   Vue large   : UN local Appartement + N dépendances acceptées (323 194 ventes exclues récupérées, 80%)
--
-- Règles appliquées (identiques sauf règle 2) :
--   1. nature_mutation = 'Vente'
--   2. La mutation contient UN SEUL local NON-DÉPENDANCE, et ce local est un Appartement
--      (les Dépendances sont ignorées dans le comptage)
--   3. surface_reelle_bati > 0 (surface de l'appartement)
--   4. Prix au m² entre 500 et 30 000 EUR
--
-- DÉCISION UTILISATEUR REQUISE :
-- Cette vue est fournie comme option. Créez-la seulement si vous acceptez le trade-off :
--   + Couverture : de 72 057 à 355 024 ventes après filtre de prix (x4,9), de 4 219 à 6 937 communes (mesuré le 19/11/2026)
--   - Précision : le prix au m² inclut la valeur foncière totale (appartement + dépendances)
--                 divisée par la surface de l'appartement seul
--
-- Pour créer cette vue :
--   docker compose exec db psql -U immo_admin -d immo -f /sql/05_view_alternative_coverage.sql
--
-- Pour créer la vue matérialisée correspondante :
--   CREATE MATERIALIZED VIEW immo.v_prix_m2_commune_large_mat AS
--   SELECT * FROM immo.v_prix_m2_commune_large;
--   CREATE INDEX ON immo.v_prix_m2_commune_large_mat (code_commune, annee);
--
-- Exécuté par immo_admin. Idempotent.

SET search_path = immo;

CREATE OR REPLACE VIEW immo.v_prix_m2_commune_large AS
WITH mutations AS (
    -- Une ligne par mutation 'Vente', avec les attributs de son local PRINCIPAL (hors dépendances)
    SELECT d.id_mutation,
           count(*) FILTER (WHERE d.type_local IS NOT NULL
                            AND d.type_local <> 'Dépendance')                AS nb_locaux_principaux,
           bool_or(d.type_local = 'Appartement')                             AS local_appartement,
           max(d.code_commune)        FILTER (WHERE d.type_local = 'Appartement') AS code_commune,
           max(d.nom_commune)         FILTER (WHERE d.type_local = 'Appartement') AS nom_commune_dvf,
           max(d.date_mutation)                                              AS date_mutation,
           max(d.valeur_fonciere)     FILTER (WHERE d.type_local = 'Appartement') AS valeur_fonciere,
           max(d.surface_reelle_bati) FILTER (WHERE d.type_local = 'Appartement') AS surface_reelle_bati
    FROM immo.dvf_mutations d
    WHERE d.nature_mutation = 'Vente'
    GROUP BY d.id_mutation
),
ventes AS (
    SELECT m.*, m.valeur_fonciere / m.surface_reelle_bati AS prix_m2
    FROM mutations m
    WHERE m.nb_locaux_principaux = 1 AND m.local_appartement
      AND m.surface_reelle_bati > 0
)
SELECT v.code_commune,
       coalesce(c.libelle, v.nom_commune_dvf)          AS nom_commune,
       extract(year FROM v.date_mutation)::int         AS annee,
       count(*)                                        AS nb_ventes,
       round(avg(v.prix_m2))::integer                  AS prix_m2_moyen
FROM ventes v
LEFT JOIN immo.insee_communes c ON c.code_insee = v.code_commune
WHERE v.prix_m2 BETWEEN 500 AND 30000
GROUP BY v.code_commune, coalesce(c.libelle, v.nom_commune_dvf), extract(year FROM v.date_mutation);

COMMENT ON VIEW immo.v_prix_m2_commune_large IS
    'Vue ALTERNATIVE de v_prix_m2_commune avec couverture élargie : ignore les dépendances (caves, parkings) dans le comptage des locaux. Passe de 72 057 à 355 024 ventes (x4,9), mais le prix au m² inclut la valeur totale (appartement + dépendances) / surface appartement seul. Utiliser selon le cas d''usage.';
