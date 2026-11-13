-- Vues analytiques.
--
-- EN ATTENTE des en-têtes réels. Règles validées pour v_prix_m2_commune :
--   - nature de mutation = 'Vente'
--   - mutations comportant un seul local, de type Appartement
--   - surface réelle bâtie renseignée et > 0
--   - prix au m² compris dans [500 ; 30 000] EUR
--   - agrégation : prix au m² moyen par commune et par année

SET search_path = immo;

-- CREATE OR REPLACE VIEW immo.v_prix_m2_commune AS ... ;   -- à compléter
