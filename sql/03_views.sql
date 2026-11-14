-- Vues analytiques (schéma immo).
-- Exécuté par immo_admin (propriétaire du schéma). analyst_ro reçoit SELECT par les droits
-- par défaut (ALTER DEFAULT PRIVILEGES FOR ROLE immo_admin, cf. 01_roles.sql).
-- Idempotent : CREATE OR REPLACE VIEW.

SET search_path = immo;

-- ---------------------------------------------------------------------------
-- v_prix_m2_commune : prix moyen au m² des appartements, par commune et par année
-- ---------------------------------------------------------------------------
-- Règles validées :
--   1. nature_mutation = 'Vente' (valeur exacte : les VEFA, adjudications, etc. sont exclues) ;
--   2. la mutation contient UN SEUL local (ligne où type_local est renseigné), et ce local est
--      de type 'Appartement'. Une vente appartement + dépendance (cave, parking) compte deux
--      locaux et est donc exclue. Les lignes sans local (parcelles) ne comptent pas ;
--   3. surface_reelle_bati > 0 (surface du local) ;
--   4. prix au m² = valeur_fonciere / surface_reelle_bati, compris entre 500 et 30 000 EUR
--      (bornes incluses).
-- Agrégation : par commune (code du local) et par année de mutation ; prix_m2_moyen est la
-- moyenne des prix au m² des ventes retenues (moyenne de ratios), arrondie à l'euro.
-- Commune : libellé du COG ; pour un code absent du référentiel (cf. docs/sources.md), le nom
-- figurant dans DVF.
--
-- Constat sur DVF 2025 : sur 1 309 960 mutations « Vente », 81 133 comportent un seul local de
-- type Appartement, contre 323 194 ventes d'appartement accompagnées d'autres locaux (le plus
-- souvent des dépendances), exclues par la règle 2.

CREATE OR REPLACE VIEW immo.v_prix_m2_commune AS
WITH mutations AS (
    -- Une ligne par mutation « Vente », avec les attributs de son local
    SELECT d.id_mutation,
           count(*) FILTER (WHERE d.type_local IS NOT NULL)                   AS nb_locaux,
           bool_or(d.type_local = 'Appartement')                             AS local_appartement,
           max(d.code_commune)        FILTER (WHERE d.type_local IS NOT NULL) AS code_commune,
           max(d.nom_commune)         FILTER (WHERE d.type_local IS NOT NULL) AS nom_commune_dvf,
           max(d.date_mutation)                                              AS date_mutation,
           max(d.valeur_fonciere)     FILTER (WHERE d.type_local IS NOT NULL) AS valeur_fonciere,
           max(d.surface_reelle_bati) FILTER (WHERE d.type_local IS NOT NULL) AS surface_reelle_bati
    FROM immo.dvf_mutations d
    WHERE d.nature_mutation = 'Vente'                                  -- règle 1
    GROUP BY d.id_mutation
),
ventes AS (
    SELECT m.*, m.valeur_fonciere / m.surface_reelle_bati AS prix_m2
    FROM mutations m
    WHERE m.nb_locaux = 1 AND m.local_appartement                      -- règle 2
      AND m.surface_reelle_bati > 0                                    -- règle 3
)
SELECT v.code_commune,
       coalesce(c.libelle, v.nom_commune_dvf)          AS nom_commune,
       extract(year FROM v.date_mutation)::int         AS annee,
       count(*)                                        AS nb_ventes,
       round(avg(v.prix_m2))::integer                  AS prix_m2_moyen
FROM ventes v
LEFT JOIN immo.insee_communes c ON c.code_insee = v.code_commune
WHERE v.prix_m2 BETWEEN 500 AND 30000                                  -- règle 4
GROUP BY v.code_commune, coalesce(c.libelle, v.nom_commune_dvf), extract(year FROM v.date_mutation);

COMMENT ON VIEW immo.v_prix_m2_commune IS
    'Prix moyen au m² des appartements par commune et par année (DVF). Ventes simples : nature_mutation = Vente, un seul local de type Appartement, surface_reelle_bati > 0, prix au m² entre 500 et 30 000 EUR.';
COMMENT ON COLUMN immo.v_prix_m2_commune.nb_ventes     IS 'Nombre de mutations retenues';
COMMENT ON COLUMN immo.v_prix_m2_commune.prix_m2_moyen IS 'Moyenne des prix au m² (valeur_fonciere / surface_reelle_bati) des ventes retenues, en euros';
