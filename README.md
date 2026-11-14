# Agent de gestion de base de données : marché immobilier français

Base PostgreSQL 16 destinée à un agent qui analyse les requêtes SQL : repérer les requêtes
coûteuses, lire leurs plans `EXPLAIN`, expliquer leur lenteur, proposer des index ou des
réécritures, et traduire des questions métier en SQL. **L'agent ne modifie jamais la structure de
la base sans validation humaine** : il se connecte avec un rôle en lecture seule (`analyst_ro`).

Données : deux sources publiques reliées par le code commune INSEE.

| Source | Contenu | Table | Volume |
|---|---|---|---|
| DVF géolocalisé (Etalab), 2025 | transactions immobilières | `immo.dvf_mutations` | 3 793 113 lignes, environ 1,6 Go |
| COG INSEE 2026 et populations de référence 2023 | communes et arrondissements municipaux, avec leur population | `immo.insee_communes` | 34 920 lignes |

Phase 1 terminée : infrastructure, schéma, chargement, vérification, vue de prix au m².

## Sommaire

- [Arborescence](#arborescence)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Chargement des données](#chargement-des-données)
- [Vérification](#vérification)
- [Se connecter](#se-connecter)
- [Requêtes d'exemple](#requêtes-dexemple)
- [La vue v_prix_m2_commune](#la-vue-v_prix_m2_commune)
- [Codes orphelins](#codes-orphelins)
- [Sécurité](#sécurité)
- [Limites connues](#limites-connues)
- [Points ouverts](#points-ouverts)

## Arborescence

```
DATAIA_project/
├── data/raw/                  # fichiers bruts (non versionnés, cf. docs/sources.md)
├── docs/
│   ├── sources.md             # provenance des données, codes hors référentiel
│   └── securite.md            # rôles, authentification, droits sensibles, incidents
├── scripts/
│   ├── _common.ps1            # fonctions partagées (lecture de .env, appel de psql dans le conteneur)
│   ├── init-db.ps1            # extension, rôles, schémas, tables, vues (idempotent)
│   ├── load.ps1               # chargement des CSV (staging puis INSERT typé), option -DryRun
│   └── verify.ps1             # compteurs, valeurs nulles, codes orphelins, droits des rôles
├── sql/
│   ├── 00_extensions.sql      # pg_stat_statements                       (postgres)
│   ├── 01_roles.sql           # rôles immo_admin et analyst_ro, schémas  (postgres)
│   ├── 02_schema.sql          # tables et index                          (immo_admin)
│   ├── 03_views.sql           # vue v_prix_m2_commune                    (immo_admin)
│   ├── verify.sql             # contrôles lancés par verify.ps1          (analyst_ro)
│   └── load/                  # tables de transit et scripts de chargement (immo_admin)
├── docker-compose.yml         # PostgreSQL 16 et pg_stat_statements
├── .env.example               # modèle de configuration (copier en .env)
└── README.md
```

## Prérequis

- **Docker Desktop** (Docker Compose v2).
- **Windows PowerShell 5.1** ou plus récent : les scripts sont en PowerShell.
- **psql n'est pas nécessaire** sur la machine : les scripts l'exécutent dans le conteneur.
- Environ **4 Go d'espace disque** : 0,85 Go de fichiers bruts, 1,6 Go pour la table DVF, plus
  de l'espace temporaire pendant le chargement.

## Installation

1. **Configurer** : copier `.env.example` en `.env`, puis remplacer chaque `a_remplacer` par un
   mot de passe. `.env` n'est jamais versionné.

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   | Variable | Rôle |
   |---|---|
   | `POSTGRES_USER`, `POSTGRES_PASSWORD` | superutilisateur technique, réservé à l'administration |
   | `POSTGRES_DB` | nom de la base (`immo`) |
   | `POSTGRES_PORT` | port publié sur `127.0.0.1` (5432 par défaut ; mettre 5433 si 5432 est déjà pris) |
   | `IMMO_ADMIN_PASSWORD` | propriétaire des schémas, chargement des données |
   | `ANALYST_RO_PASSWORD` | rôle en lecture seule de l'agent |

2. **Démarrer et initialiser** :

   ```powershell
   .\scripts\init-db.ps1
   ```

   Ce script lance le conteneur, puis crée l'extension `pg_stat_statements`, les rôles, les
   schémas `immo` et `immo_staging`, les tables et la vue. Il peut être rejoué sans risque : il
   ne supprime ni ne modifie aucune donnée.

3. **Exiger un mot de passe pour les connexions locales**. Sur un volume neuf, l'image officielle
   `postgres` autorise les connexions locales au conteneur sans mot de passe (`trust`). Ce projet
   les passe en `scram-sha-256`. Cette modification est stockée dans le volume, pas dans le dépôt :
   elle est à refaire après chaque création de volume. La procédure est décrite dans
   [docs/securite.md](docs/securite.md#authentification--mot-de-passe-exigé-partout-scram-sha-256).

## Chargement des données

1. **Télécharger** les fichiers dans `data/raw/`. La provenance et les liens sont dans
   [docs/sources.md](docs/sources.md). Noms attendus par défaut :

   ```
   data/raw/dvf_2025.csv                                        # DVF géolocalisé 2025, décompressé
   data/raw/v_commune_2026.csv                                  # COG 2026, communes
   data/raw/populations_reference_2023/donnees_communes.csv     # extrait de ensemble.zip
   ```

2. **Tester** le chargement sans rien persister (`BEGIN … ROLLBACK`) :

   ```powershell
   .\scripts\load.ps1 -DryRun
   ```

3. **Charger** pour de bon (environ 8 minutes) :

   ```powershell
   .\scripts\load.ps1
   ```

Fonctionnement : chaque fichier est lu par `COPY` dans une table de transit de `immo_staging`,
toutes colonnes en texte. L'option `HEADER MATCH` refuse un fichier dont l'en-tête aurait changé.
Les données sont ensuite converties et insérées dans les tables finales, en une seule transaction
par fichier : tout passe, ou rien ne passe. Tout le chargement s'exécute en tant que `immo_admin`.

**Garde-fous** : le chargement ne modifie jamais de données existantes.

- `insee_communes` : refusé si la table contient déjà des lignes.
- `dvf_mutations` : refusé si la table contient déjà au moins une mutation sur la période du
  fichier (dates minimale et maximale, bornes incluses). Une autre année peut donc être ajoutée
  sans toucher aux précédentes :

  ```powershell
  .\scripts\load.ps1 -Only dvf -DvfFile dvf_2024.csv
  ```

- Pour recharger une période déjà présente, il faut d'abord supprimer ses lignes à la main.
  Ce choix est volontaire : aucun script ne le fait.

## Vérification

```powershell
.\scripts\verify.ps1
```

Le script s'exécute en tant que `analyst_ro`, donc il ne peut rien modifier. Il dure environ 20 s
et affiche :

1. **les compteurs** : lignes par table, par type de commune (`COM`, `ARM`) et par année DVF ;
2. **les valeurs nulles** sur les colonnes clés de `dvf_mutations` : `code_commune`,
   `date_mutation`, `valeur_fonciere`, `surface_reelle_bati`, `type_local` ;
3. **les codes DVF absents de `insee_communes`**, avec leur nombre de lignes, marqués
   « documenté » ou « NOUVEAU ». Rien n'est corrigé ;
4. **les contrôles de rôles** :
   - lecture du catalogue : `immo_admin` n'est pas superutilisateur, `analyst_ro` n'a aucun
     droit d'écriture ni de création ;
   - tentatives réelles d'écriture et de création sous `analyst_ro` (INSERT, UPDATE, DELETE,
     TRUNCATE, COPY, ALTER, CREATE, DROP, table temporaire, lecture du staging, `pg_read_file`),
     dans une transaction annulée. Chacune doit être refusée.

Code de sortie : 0 si tous les contrôles bloquants sont OK, sinon une erreur. Le script prévoit
aussi un statut `ATTENTION`, signalé sans faire échouer la vérification ; aucun contrôle ne
l'utilise actuellement.

Résultat au 2026-11-14 : 31 OK, 0 échec, 0 ATTENTION.

| Colonne | Valeurs nulles | % des lignes |
|---|---:|---:|
| `code_commune` | 0 | 0,00 |
| `date_mutation` | 0 | 0,00 |
| `valeur_fonciere` | 50 484 | 1,33 |
| `surface_reelle_bati` | 1 499 963 | 39,54 |
| `type_local` | 1 497 725 | 39,49 |

Les nulls de `surface_reelle_bati` et `type_local` correspondent aux lignes sans local : parcelles
de terrain, ou lignes de lot.

## Se connecter

Rôle de l'agent, `analyst_ro`. Le mot de passe est demandé de façon interactive :

```powershell
docker compose exec -it db psql -U analyst_ro -d immo
```

Depuis un client SQL sur la machine (DBeaver, pgAdmin…), utiliser l'hôte `127.0.0.1`, le port
`POSTGRES_PORT` de `.env`, la base `immo`, l'utilisateur `analyst_ro`.

Paramètres de session de `analyst_ro` : `statement_timeout = 30s`, transactions en lecture seule
par défaut, `search_path = immo, public`.

## Requêtes d'exemple

Toutes ces requêtes ont été exécutées en tant que `analyst_ro`. Les durées ont été mesurées le
2026-11-14.

**Volume de lignes par type de bien** (environ 1 s) :

```sql
SELECT coalesce(type_local, '(sans local)') AS type_local,
       count(*) AS lignes,
       count(*) FILTER (WHERE nature_mutation = 'Vente') AS lignes_vente
FROM dvf_mutations
GROUP BY 1
ORDER BY 2 DESC;
```

**Transactions d'une commune**, ici Bordeaux. Le plan montre l'utilisation de l'index
`dvf_mutations_code_commune_idx` (environ 0,1 s) :

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), round(avg(valeur_fonciere))
FROM dvf_mutations
WHERE code_commune = '33063';
```

**Filtre sur une période** : aucun index sur `date_mutation`, donc PostgreSQL lit toute la table
avec un « Parallel Seq Scan » (environ 0,4 s) :

```sql
EXPLAIN ANALYZE
SELECT count(*)
FROM dvf_mutations
WHERE date_mutation BETWEEN '2025-06-01' AND '2025-06-30';
```

**Requêtes les plus coûteuses**, d'après `pg_stat_statements` :

```sql
SELECT round(total_exec_time) AS total_ms, calls, round(mean_exec_time) AS moyenne_ms,
       left(regexp_replace(query, '\s+', ' ', 'g'), 80) AS requete
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

**Communes les plus chères au m²**, appartements, au moins 100 ventes (environ 17 s, voir
ci-dessous) :

```sql
SELECT code_commune, nom_commune, nb_ventes, prix_m2_moyen
FROM v_prix_m2_commune
WHERE annee = 2025 AND nb_ventes >= 100
ORDER BY prix_m2_moyen DESC
LIMIT 10;
```

### Requêtes lentes : cas d'étude pour l'agent

La vue `v_prix_m2_commune` recalcule son agrégat sur les 3,8 millions de lignes à chaque appel.
Toute requête qui la lit prend donc **environ 17 s**, même avec un filtre sur une commune : le
filtre ne peut pas être appliqué avant le regroupement par mutation. Avec une jointure, la durée
s'approche du `statement_timeout` de 30 s :

```sql
-- Mesuré à 29,2 s : peut dépasser le timeout de 30 s d'analyst_ro
SELECT v.nom_commune, c.pmun AS population, v.nb_ventes, v.prix_m2_moyen
FROM v_prix_m2_commune v
JOIN insee_communes c ON c.code_insee = v.code_commune
WHERE c.pmun >= 100000
ORDER BY v.prix_m2_moyen DESC
LIMIT 10;
```

Pistes à étudier avec l'agent, toutes soumises à validation humaine : vue matérialisée, index,
réécriture de la requête.

## La vue v_prix_m2_commune

Prix moyen au m² des appartements, par commune et par année. Règles appliquées :

1. `nature_mutation = 'Vente'`, valeur exacte : les VEFA, adjudications et échanges sont exclus ;
2. la mutation contient **un seul local**, une ligne où `type_local` est renseigné, et ce local
   est un `Appartement` ;
3. `surface_reelle_bati > 0` ;
4. prix au m² (`valeur_fonciere / surface_reelle_bati`) **entre 500 et 30 000 €**, bornes incluses.

| Colonne | Contenu |
|---|---|
| `code_commune` | code INSEE du local (arrondissement pour Paris, Lyon et Marseille) |
| `nom_commune` | libellé du COG ; nom figurant dans DVF si le code est hors référentiel |
| `annee` | année de la mutation |
| `nb_ventes` | nombre de mutations retenues |
| `prix_m2_moyen` | moyenne des prix au m² des ventes retenues, arrondie à l'euro |

DVF 2025 : 72 057 ventes retenues, 4 219 communes couvertes, dont les 45 arrondissements. Ces
chiffres ont été recoupés par un calcul indépendant.

**À savoir** : la règle 2 est stricte. Une vente « appartement + cave » ou « appartement +
parking » compte deux locaux et est exclue. Sur 2025, **81 133** ventes ont un seul local de type
appartement, contre **323 194** ventes d'appartement accompagnées d'autres locaux.

## Codes orphelins

Il n'y a pas de clé étrangère entre `dvf_mutations` et `insee_communes`. Les codes DVF absents du
référentiel sont chargés tels quels, listés par `verify.ps1`, et ne sont jamais corrigés
automatiquement.

| Code | Nom dans DVF | Lignes 2025 | Explication |
|---|---|---:|---|
| 97127 | Saint Martin | 646 | Collectivité d'outre-mer : le COG des collectivités n'est volontairement pas chargé |
| 97123 | Saint Barthelemy (Ile) | 160 | Même cas |
| 44219 | Vritz | 4 | À identifier, probablement une ancienne commune fusionnée |
| 49069 | Oree D Anjou | 2 | À identifier |
| 49144 | Freigne | 1 | À identifier, probablement une ancienne commune fusionnée |

Pour garder ces lignes dans une jointure, utiliser `LEFT JOIN insee_communes`. Détails dans
[docs/sources.md](docs/sources.md#codes-dvf-hors-référentiel).

Côté référentiel, 20 codes n'ont pas de population : Paris (75056), Lyon (69123) et Marseille
(13055), dont la population est publiée par arrondissement, et les 17 communes de Mayotte, absentes
du fichier « France hors Mayotte ».

## Sécurité

Résumé. Le détail, les vérifications et l'historique sont dans [docs/securite.md](docs/securite.md).

| Rôle | Superutilisateur | Usage |
|---|---|---|
| `postgres` | oui (compte d'initialisation) | extension, rôles, schémas uniquement |
| `immo_admin` | **non** | propriétaire de `immo` et `immo_staging`, chargement (`pg_read_server_files`) |
| `analyst_ro` | non | agent : `SELECT` sur `immo` uniquement, aucune création (même temporaire), timeout de 30 s, lecture seule par défaut, `pg_stat_statements` |

- Aucun mot de passe dans le code : tout vient de `.env`, qui n'est pas versionné. Les scripts
  transmettent le mot de passe à psql par `PGPASSWORD`, jamais sur la ligne de commande.
- Mot de passe exigé pour toute connexion (`scram-sha-256`), y compris à l'intérieur du conteneur.
- Droit `TEMP` retiré à `PUBLIC` : `analyst_ro` ne peut pas créer de table temporaire, même en
  désactivant la lecture seule.
- Port publié uniquement sur `127.0.0.1` ; `data/raw` et `sql` montés en lecture seule.
- `pg_read_server_files`, accordé à `immo_admin`, reste un **droit sensible** : il permet de lire
  n'importe quel fichier accessible au serveur PostgreSQL.
- `init: true` dans `docker-compose.yml` : un vrai processus init récupère les processus
  orphelins du conteneur. Voir l'incident du 2026-11-13 dans `docs/securite.md`.

## Limites connues

- **La vue ne retient que les ventes avec un seul local.** `v_prix_m2_commune` exclut toute vente
  qui comporte, en plus de l'appartement, un autre local : dépendance (cave, parking), maison ou
  local commercial. Cela écarte **environ 80 % des ventes d'appartements** : sur 2025, 323 194
  ventes d'appartement avec d'autres locaux, contre 81 133 avec un seul local. Les prix moyens
  portent donc sur un sous-ensemble de ventes « simples ». Une variante qui ignorerait les
  dépendances reste à décider.
- **La vue est lente : environ 17 s par lecture.** Elle recalcule l'agrégat sur les 3,8 millions
  de lignes DVF à chaque appel, même avec un filtre sur une commune. Avec une jointure, la durée
  approche le `statement_timeout` de 30 s d'`analyst_ro` (29,2 s mesurées). Voir
  [Requêtes lentes](#requêtes-lentes--cas-détude-pour-lagent).
- **Les codes orphelins sont documentés, pas corrigés.** 5 codes DVF (813 lignes en 2025) sont
  absents du référentiel INSEE. Ils sont expliqués dans [Codes orphelins](#codes-orphelins) et
  [docs/sources.md](docs/sources.md#codes-dvf-hors-référentiel), et listés à chaque exécution de
  `verify.ps1`. Les jointures avec `insee_communes` doivent être des `LEFT JOIN` pour garder ces
  lignes.

## Points ouverts

- **Volume neuf** : la configuration `scram-sha-256` des connexions locales est à refaire (voir
  [Installation](#installation), étape 3).
- **Codes 44219, 49069, 49144** : leur origine reste à confirmer avec `v_mvt_commune_2026` (COG).
