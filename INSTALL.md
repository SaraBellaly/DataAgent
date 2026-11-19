# Guide d'installation pour l'évaluation

Ce document décrit, étape par étape, comment installer le projet sur votre machine pour
l'évaluer. Chaque étape indique le résultat attendu. Il suffit de suivre l'ordre du document.

## 1. Objet du projet

Une base PostgreSQL 16 sur le marché immobilier français : transactions DVF 2025 et communes
INSEE, reliées par le code commune. Elle sert de terrain à un agent qui analyse les requêtes SQL
(requêtes coûteuses, plans `EXPLAIN`, index, réécritures). L'agent n'y accède qu'en lecture seule.

**À la fin de ce guide**, vous aurez :

- un conteneur PostgreSQL 16 sur votre machine, avec `pg_stat_statements` activé ;
- deux tables chargées : 34 920 communes et 3 793 113 lignes de transactions ;
- une vue de prix au m² par commune, et sa version matérialisée (moins de 2 ms par requête) ;
- trois rôles de travail : `immo_admin` (chargement), `analyst_ro` (lecture seule, pour l'agent)
  et `app_agent` (comptes, sessions et historique de l'application) ;
- l'application FastAPI (authentification et historique) sur `http://127.0.0.1:8000`, avec ses
  31 tests automatiques ;
- un script de vérification dont le résultat attendu est **38 OK, 0 échec, 0 ATTENTION**.

Durée totale : environ 30 minutes, dont 8 minutes de chargement. Le téléchargement des données
(environ 120 Mo) dépend de votre connexion.

## 2. Prérequis

| Outil | Version | Vérification |
|---|---|---|
| Docker Desktop | récent, avec Docker Compose v2 (testé : Docker 29.9, Compose v5.7) | `docker compose version` |
| PowerShell | Windows : **Windows PowerShell 5.1** (fourni avec Windows 10/11). macOS ou Linux : **PowerShell 7 ou plus** (`pwsh`) | `$PSVersionTable.PSVersion` |
| Git | toute version récente | `git --version` |
| Espace disque | **environ 5 Go** libres | |

Les scripts ont été testés **sous Windows avec Windows PowerShell 5.1**. Ils devraient fonctionner
sous PowerShell 7 sur macOS et Linux, mais cela n'a **pas été testé**.

Vous n'avez **pas besoin d'installer PostgreSQL ni psql** : les scripts exécutent psql à
l'intérieur du conteneur.

**Le port 5433 doit être libre** sur votre machine. Vérification :

```powershell
# Windows : aucune ligne affichée = port libre
Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue

# macOS / Linux : aucune ligne affichée = port libre
lsof -i :5433
```

Si le port 5433 est déjà pris, choisissez un autre port libre et indiquez-le à l'étape 4.

**Docker Desktop doit être démarré** avant de continuer : son icône indique que le moteur est
« running ».

## 3. Récupération du projet

```powershell
git clone https://github.com/SaraBellaly/DataAgent.git
cd DataAgent
```

Toutes les commandes suivantes se lancent **depuis ce dossier `DataAgent`**.

**Windows uniquement** : autorisez l'exécution des scripts PowerShell pour la session en cours. Ce
réglage ne concerne que cette fenêtre et disparaît à sa fermeture :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Sans cela, Windows peut refuser de lancer `.\scripts\*.ps1` (voir [Dépannage](#10-dépannage)).

## 4. Configuration

Copiez le modèle de configuration :

```powershell
Copy-Item .env.example .env
```

Ouvrez `.env` dans un éditeur (par exemple `notepad .env` sous Windows) et modifiez-le ainsi :

1. Remplacez chaque `a_remplacer` par un mot de passe : il y en a **quatre**,
   `POSTGRES_PASSWORD`, `IMMO_ADMIN_PASSWORD`, `ANALYST_RO_PASSWORD` et `APP_AGENT_PASSWORD`
   (rôle de l'application : comptes, sessions, historique).
2. Remplacez `POSTGRES_PORT=5432` par **`POSTGRES_PORT=5433`**, ou par le port libre choisi à
   l'étape 2.

Pour les mots de passe, utilisez **uniquement des lettres et des chiffres** : pas de guillemets,
d'espaces, ni de `$` ou de `#`. Ces caractères seraient interprétés différemment par Docker Compose
et par les scripts, et l'authentification échouerait. Pour générer un mot de passe de 24
caractères :

```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
```

Résultat attendu : un fichier `.env` de ce type, avec vos propres valeurs.

```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<votre mot de passe 1>
POSTGRES_DB=immo
POSTGRES_PORT=5433
IMMO_ADMIN_PASSWORD=<votre mot de passe 2>
ANALYST_RO_PASSWORD=<votre mot de passe 3>
APP_AGENT_PASSWORD=<votre mot de passe 4>
APP_PORT=8000
COOKIE_SECURE=false
```

> **`.env` ne doit jamais être commité.** Il contient les mots de passe en clair. Le fichier
> `.gitignore` du projet l'exclut déjà ; ne forcez pas son ajout (`git add -f .env`). Seul
> `.env.example`, qui ne contient que des valeurs d'exemple, est versionné.

**Gardez ces mots de passe.** `POSTGRES_PASSWORD` est fixé lors de la toute première création de
la base : le modifier ensuite dans `.env` empêche les scripts de se connecter (voir
[Dépannage](#mot-de-passe-refusé)).

## 5. Téléchargement des données

Les données ne sont pas dans le dépôt Git. Elles se placent dans `data/raw/` : trois fichiers sont
utilisés, aux noms exacts suivants.

| Fichier attendu dans `data/raw/` | Source | Taille |
|---|---|---|
| `dvf_2025.csv` | DVF géolocalisé (Etalab), année 2025 | 731 194 611 octets (environ 697 Mo) |
| `v_commune_2026.csv` | INSEE, Code officiel géographique 2026, communes | 3 565 935 octets |
| `populations_reference_2023/donnees_communes.csv` | INSEE, populations de référence 2023 | 2 167 955 octets |

Les commandes ci-dessous fonctionnent sous Windows PowerShell 5.1 et sous PowerShell 7. Lancez-les
depuis le dossier `DataAgent`. La première ligne accélère `Invoke-WebRequest` sous PowerShell 5.1
en masquant la barre de progression.

```powershell
$ProgressPreference = 'SilentlyContinue'
```

### 5.1 DVF géolocalisé 2025 (fichier `dvf_2025.csv`)

- Page du jeu de données : https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres-geolocalisees/
- L'adresse du fichier change à chaque nouvelle publication. On la récupère donc par l'API de
  data.gouv.fr, à partir de l'identifiant du jeu de données (`5cc1b94a634f4165e96436c1`). On
  sélectionne la ressource intitulée « DVF 2025 », au format `csv.gz`.

```powershell
# 1. Trouver l'URL du fichier DVF 2025 (csv.gz)
$api = Invoke-RestMethod "https://www.data.gouv.fr/api/1/datasets/5cc1b94a634f4165e96436c1/"
$dvf = $api.resources | Where-Object { $_.title -eq 'DVF 2025' -and $_.format -eq 'csv.gz' }
$dvf.url

# 2. Télécharger l'archive (environ 116 Mo)
Invoke-WebRequest -Uri $dvf.url -OutFile "data/raw/dvf_2025.csv.gz" -UseBasicParsing

# 3. Décompresser en data/raw/dvf_2025.csv (environ 697 Mo, quelques dizaines de secondes)
$gz  = (Resolve-Path "data/raw/dvf_2025.csv.gz").Path
$csv = Join-Path (Resolve-Path "data/raw").Path "dvf_2025.csv"
$in  = [IO.File]::OpenRead($gz)
$unz = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
$out = [IO.File]::Create($csv)
$unz.CopyTo($out); $out.Close(); $unz.Close(); $in.Close()
```

Résultat attendu :

- `$dvf.url` affiche une adresse se terminant par `full-2025.csv.gz`. Lors de la préparation du
  projet, c'était
  `https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees/20261020-114721/full-2025.csv.gz`.
- `data/raw/dvf_2025.csv.gz` fait 116 267 867 octets et `data/raw/dvf_2025.csv` 731 194 611
  octets.

> Les compteurs de ce guide (3 793 113 lignes DVF, etc.) correspondent à la publication du
> 20 octobre 2026, visible dans l'URL ci-dessus. Si data.gouv.fr a republié le fichier 2025
> depuis, les tailles et les compteurs peuvent légèrement différer.

L'archive `.csv.gz` n'est plus utilisée après décompression ; vous pouvez la conserver ou la
supprimer.

### 5.2 Communes du COG 2026 (fichier `v_commune_2026.csv`)

- Page : https://www.insee.fr/fr/information/2560452 (Code officiel géographique), puis
  « Millésime 2026 : Téléchargement des fichiers » (https://www.insee.fr/fr/information/8740222).
- Fichier : la liste des communes au format CSV, téléchargée directement sous le bon nom :

```powershell
Invoke-WebRequest -Uri "https://www.insee.fr/fr/statistiques/fichier/8740222/v_commune_2026.csv" -OutFile "data/raw/v_commune_2026.csv" -UseBasicParsing
```

Résultat attendu : `data/raw/v_commune_2026.csv`, 3 565 935 octets. Sa première ligne est
`"TYPECOM","COM","REG","DEP","CTCD","ARR","TNCC","NCC","NCCENR","LIBELLE","CAN","COMPARENT"`.

Le serveur de l'INSEE a déjà renvoyé une erreur passagère `500 Internal Server Error` sur cette
adresse. Dans ce cas, réessayez quelques minutes plus tard.

### 5.3 Populations de référence 2023 (fichier `populations_reference_2023/donnees_communes.csv`)

Depuis le millésime 2022, l'INSEE parle de « populations de référence » et non plus de
« populations légales ». On utilise le fichier d'ensemble 2023 (France hors Mayotte).

- Page : https://www.insee.fr/fr/statistiques/8680726?sommaire=8681011
- Fichier : `ensemble.zip`, version CSV. On l'enregistre sous le nom
  `populations_reference_2023_ensemble.zip`, puis on le dézippe dans le dossier
  `data/raw/populations_reference_2023/`.

```powershell
Invoke-WebRequest -Uri "https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.zip" -OutFile "data/raw/populations_reference_2023_ensemble.zip" -UseBasicParsing
Expand-Archive -Path "data/raw/populations_reference_2023_ensemble.zip" -DestinationPath "data/raw/populations_reference_2023"
```

Résultat attendu :

- l'archive fait 1 032 385 octets ;
- le dossier `data/raw/populations_reference_2023/` contient 9 fichiers CSV. Seul
  `donnees_communes.csv` (2 167 955 octets, séparateur `;`) est chargé ;
- sa première ligne est `REG;Région;DEP;CODARR;CODCAN;CODCOM;COM;Commune;PMUN;PCAP;PTOT`.

### 5.4 Contrôle

```powershell
Get-Item data/raw/dvf_2025.csv, data/raw/v_commune_2026.csv, data/raw/populations_reference_2023/donnees_communes.csv | Select-Object Name, Length
```

Résultat attendu :

```
Name                    Length
----                    ------
dvf_2025.csv         731194611
v_commune_2026.csv     3565935
donnees_communes.csv   2167955
```

La provenance détaillée des données est décrite dans [docs/sources.md](docs/sources.md).

## 6. Démarrage

### 6.1 Lancer le conteneur

```powershell
docker compose up -d db
```

Lors du premier lancement, Docker télécharge l'image `postgres:16`, puis initialise la base.
Attendez que l'initialisation soit terminée :

```powershell
docker compose logs db | Select-String "init process complete"
```

Résultat attendu : une ligne contenant `PostgreSQL init process complete; ready for start up.`. Si
rien ne s'affiche, patientez quelques secondes et relancez la commande.

### 6.2 Créer l'extension, les rôles, les schémas, les tables et la vue

```powershell
.\scripts\init-db.ps1
```

Sous macOS et Linux, depuis `pwsh`, utilisez `./scripts/init-db.ps1`. Il en va de même pour les
autres scripts.

Résultat attendu : le script affiche chaque fichier SQL exécuté, avec le rôle utilisé, puis
termine par la ligne verte `Initialisation terminee.`

```
>> /sql/00_extensions.sql
CREATE EXTENSION
>> /sql/01_roles.sql
CREATE ROLE
ALTER ROLE
...
>> /sql/02_schema.sql (en tant que immo_admin)
...
CREATE TABLE
...
CREATE INDEX
>> /sql/03_views.sql (en tant que immo_admin)
...
CREATE VIEW
...
>> /sql/06_app_schema.sql (en tant que immo_admin)
CREATE TABLE
...
GRANT
Initialisation terminee.
```

Le script peut être relancé sans risque : il ne supprime ni ne modifie aucune donnée. Lors d'une
seconde exécution, des messages `NOTICE: ... already exists, skipping` sont normaux.

### 6.3 Exiger un mot de passe pour les connexions locales (recommandé)

Sur une base neuve, l'image officielle `postgres` laisse se connecter **sans mot de passe** depuis
l'intérieur du conteneur. Ce projet exige un mot de passe partout (`scram-sha-256`). Cette
modification n'est pas automatique ; voici comment la faire :

```powershell
docker compose exec -u postgres db cp /var/lib/postgresql/data/pg_hba.conf /var/lib/postgresql/data/pg_hba.conf.bak_trust
docker compose exec -u postgres db sed -i -E '/^[[:space:]]*#/! s/[[:space:]]+trust[[:space:]]*$/ scram-sha-256/' /var/lib/postgresql/data/pg_hba.conf
docker compose exec -u postgres db psql -U postgres -c "SELECT pg_reload_conf();"
```

Résultat attendu : la dernière commande affiche `pg_reload_conf` suivi de `t`. Les scripts du
projet fournissent automatiquement les mots de passe de `.env` et continuent de fonctionner.

Pour vérifier qu'une connexion sans mot de passe est désormais refusée :

```powershell
docker compose exec db psql -w -U postgres -d immo -c "select 1"
```

Résultat attendu : `fe_sendauth: no password supplied`.

Le contexte et la procédure de retour en arrière sont décrits dans
[docs/securite.md](docs/securite.md).

## 7. Chargement des données

```powershell
.\scripts\load.ps1
```

**Durée attendue : environ 8 minutes** (465 secondes mesurées lors de la préparation). Le script
lit les fichiers, les convertit et les insère en tant que `immo_admin`, en une transaction par
fichier : soit tout est chargé, soit rien.

Résultat attendu, en abrégé :

```
>> /sql/load/00_staging.sql (en tant que immo_admin)
>> /sql/load/10_load_insee.sql (en tant que immo_admin)
COPY 37496
COPY 34900
INSERT 0 34920
 typecom | nb_lignes | avec_population
---------+-----------+-----------------
 ARM     |        45 |              45
 COM     |     34875 |           34855
>> /sql/load/20_load_dvf.sql (en tant que immo_admin)
COPY 3793113
 lignes_staging |  date_min  |  date_max
----------------+------------+------------
        3793113 | 2025-01-01 | 2025-12-31
INSERT 0 3793113
 annee | nb_lignes
-------+-----------
  2025 |   3793113
Chargement termine en ... s.
```

Compteurs attendus :

- **34 920 lignes** dans `immo.insee_communes`, soit 34 875 communes et 45 arrondissements de
  Paris, Lyon et Marseille ;
- **3 793 113 lignes** dans `immo.dvf_mutations`.

Facultatif : pour tester le chargement sans rien enregistrer (environ 6 minutes), lancez-le
**avant** le chargement réel :

```powershell
.\scripts\load.ps1 -DryRun
```

Le script s'exécute alors dans une transaction annulée à la fin (`BEGIN … ROLLBACK`).

**Garde-fou** : un second `.\scripts\load.ps1` est **refusé**, avec un message `chargement refuse
(rien n'a ete modifie)`. C'est voulu : le chargement ne modifie jamais des données existantes.

### 7.1 Vue matérialisée des prix au m²

La vue `v_prix_m2_commune` recalcule son agrégat sur 3,8 millions de lignes à chaque lecture
(5 à 55 s). Sa version matérialisée, indexée, se calcule une fois après le chargement :

```powershell
.\scripts\create-mat-view.ps1
```

Résultat attendu, en quelques secondes : `lignes_vue_mat` = **4219**, puis la ligne verte
`Vue materialisee creee avec succes.` Après tout nouveau chargement, rafraîchissez-la avec
`.\scriptsefresh-mat-view.ps1`.

## 8. Vérification

```powershell
.\scripts\verify.ps1
```

Le script s'exécute en tant que `analyst_ro`, le rôle en lecture seule : il ne peut rien
modifier. Il dure environ 20 secondes.

Résultat attendu :

1. **Compteurs** : 34 920 lignes dans `immo.insee_communes` et 3 793 113 dans `immo.dvf_mutations`
   (année 2025, du 2025-01-01 au 2025-12-31).
2. **Valeurs nulles** : 0 sur `code_commune` et `date_mutation` ; 50 484 sur `valeur_fonciere` ;
   1 499 963 sur `surface_reelle_bati` ; 1 497 725 sur `type_local`.
3. **Codes DVF absents du référentiel INSEE** : 5 codes, tous marqués `documenté` : 97127 (646
   lignes), 97123 (160), 44219 (4), 49069 (2), 49144 (1).
4. **Contrôles de rôles** : tous `OK`.
5. **Synthèse** :

```
 ok | echecs | attention
----+--------+-----------
 38 |      0 |         0

Verification terminee : tous les controles bloquants sont OK.
```

### 8.1 Application et tests automatiques

L'application FastAPI (inscription, connexion, historique) tourne dans un second conteneur :

```powershell
docker compose up -d --build backend
```

Résultat attendu : `http://127.0.0.1:8000/health/db` (port `APP_PORT` de `.env`) renvoie
`"status":"connected"` et `"user":"analyst_ro"`. La documentation interactive de l'API est sur
`http://127.0.0.1:8000/docs`.

Les tests nécessitent Python 3.11 ; ils utilisent la base réelle et suppriment leurs comptes de
test à la fin :

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pytest
cd ..
```

Résultat attendu : `31 passed`.

## 9. Requêtes d'exemple

Ouvrez une session SQL avec le rôle de l'agent. Le mot de passe demandé est
`ANALYST_RO_PASSWORD`, celui de votre `.env` :

```powershell
docker compose exec -it db psql -U analyst_ro -d immo
```

Collez ensuite chaque requête, terminée par `;`. Pour quitter : `\q`.

Le rôle `analyst_ro` a un **délai maximal de 30 secondes par requête** (`statement_timeout`).
Les requêtes sur la vue `v_prix_m2_commune` peuvent le dépasser (voir 9.5). Les durées indiquées
ont été mesurées lors de la préparation ; elles dépendent de votre machine.

### 9.1 Volume de lignes par type de bien (environ 1 à 7 s)

```sql
SELECT coalesce(type_local, '(sans local)') AS type_local,
       count(*) AS lignes,
       count(*) FILTER (WHERE nature_mutation = 'Vente') AS lignes_vente
FROM dvf_mutations
GROUP BY 1
ORDER BY 2 DESC;
```

Résultat attendu :

```
                type_local                | lignes  | lignes_vente
------------------------------------------+---------+--------------
 (sans local)                             | 1497725 |      1328137
 Dépendance                               | 1018269 |       998724
 Maison                                   |  630001 |       626815
 Appartement                              |  526412 |       514265
 Local industriel. commercial ou assimilé |  120706 |       117372
```

### 9.2 Transactions d'une commune (Bordeaux, environ 0,1 s)

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), round(avg(valeur_fonciere))
FROM dvf_mutations
WHERE code_commune = '33063';
```

Résultat attendu : le plan contient
`Index Scan using dvf_mutations_code_commune_idx on dvf_mutations`, avec `rows=15476` dans la
partie `actual`. Sans `EXPLAIN (ANALYZE, BUFFERS)`, la requête renvoie `15476 | 1661161` : le
nombre de lignes et la valeur foncière moyenne en euros.

### 9.3 Filtre sur une période (environ 0,4 à 1 s)

```sql
EXPLAIN ANALYZE
SELECT count(*)
FROM dvf_mutations
WHERE date_mutation BETWEEN '2025-06-01' AND '2025-06-30';
```

Résultat attendu : le plan contient `Parallel Seq Scan on dvf_mutations`, car il n'existe pas
d'index sur `date_mutation`. Sans `EXPLAIN ANALYZE`, la requête renvoie `332952`.

### 9.4 Requêtes les plus coûteuses (`pg_stat_statements`)

```sql
SELECT round(total_exec_time) AS total_ms, calls, round(mean_exec_time) AS moyenne_ms,
       left(regexp_replace(query, '\s+', ' ', 'g'), 80) AS requete
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

Résultat attendu : jusqu'à 10 lignes. Leur contenu **dépend des requêtes déjà exécutées** sur
votre installation (chargement, vérification, requêtes précédentes). Les constantes y sont
remplacées par `$1`, `$2`, etc.

### 9.5 Requêtes sur la vue `v_prix_m2_commune` (lentes)

La vue recalcule son résultat sur les 3,8 millions de lignes à chaque lecture. Lors de la
préparation, ces requêtes ont pris **entre 15 et 55 secondes** et ont parfois dépassé la limite
de 30 secondes (`canceling statement due to statement timeout`). Pour les exécuter, relevez la
limite **pour votre session uniquement** :

```sql
SET statement_timeout = '120s';
```

Communes les plus chères au m² (appartements, au moins 100 ventes) :

```sql
SELECT code_commune, nom_commune, nb_ventes, prix_m2_moyen
FROM v_prix_m2_commune
WHERE annee = 2025 AND nb_ventes >= 100
ORDER BY prix_m2_moyen DESC
LIMIT 10;
```

Résultat attendu :

```
 code_commune |       nom_commune        | nb_ventes | prix_m2_moyen
--------------+--------------------------+-----------+---------------
 75106        | Paris 6e Arrondissement  |       327 |         13893
 75107        | Paris 7e Arrondissement  |       268 |         13209
 75104        | Paris 4e Arrondissement  |       254 |         12460
 75101        | Paris 1er Arrondissement |       160 |         12318
 75103        | Paris 3e Arrondissement  |       386 |         11756
 75105        | Paris 5e Arrondissement  |       385 |         11664
 75108        | Paris 8e Arrondissement  |       202 |         11459
 75102        | Paris 2e Arrondissement  |       252 |         10830
 75116        | Paris 16e Arrondissement |       559 |         10511
 75109        | Paris 9e Arrondissement  |       504 |         10459
```

Jointure avec la population (communes et arrondissements d'au moins 100 000 habitants) :

```sql
SELECT v.nom_commune, c.pmun AS population, v.nb_ventes, v.prix_m2_moyen
FROM v_prix_m2_commune v
JOIN insee_communes c ON c.code_insee = v.code_commune
WHERE c.pmun >= 100000
ORDER BY v.prix_m2_moyen DESC
LIMIT 10;
```

Résultat attendu :

```
       nom_commune        | population | nb_ventes | prix_m2_moyen
--------------------------+------------+-----------+---------------
 Paris 16e Arrondissement |     159386 |       559 |         10511
 Paris 17e Arrondissement |     159212 |       789 |          9755
 Paris 11e Arrondissement |     138170 |       943 |          9663
 Paris 15e Arrondissement |     229713 |       830 |          9537
 Paris 14e Arrondissement |     136455 |       432 |          9419
 Paris 12e Arrondissement |     138024 |       449 |          9150
 Paris 18e Arrondissement |     183127 |      1113 |          8973
 Paris 13e Arrondissement |     181271 |       404 |          8956
 Paris 20e Arrondissement |     185140 |       656 |          8396
 Boulogne-Billancourt     |     119019 |       289 |          8282
```

La lenteur de cette vue est documentée comme cas d'étude pour l'agent : voir la section
« Limites connues » du [README](README.md#limites-connues).

## 10. Dépannage

### Le port 5433 est déjà utilisé

- **Symptôme** : `docker compose up -d` ou `init-db.ps1` échoue avec
  `Bind for 127.0.0.1:5433 failed: port is already allocated`.
- **Cause probable** : un autre programme ou un autre conteneur, souvent un autre PostgreSQL,
  écoute déjà sur ce port.
- **Solution** : choisissez un port libre (voir l'étape 2), mettez-le dans `POSTGRES_PORT` de
  `.env`, puis relancez `docker compose up -d`. Pour identifier l'occupant : `docker ps` (colonne
  PORTS) ou, sous Windows, `Get-NetTCPConnection -LocalPort 5433 -State Listen`.

### Docker n'est pas démarré

- **Symptôme** : toute commande `docker` échoue, par exemple sous Windows avec
  `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`.
- **Cause probable** : Docker Desktop n'est pas lancé, ou son moteur est encore en cours de
  démarrage.
- **Solution** : lancez Docker Desktop et attendez que le moteur soit « running ». Vérifiez avec
  `docker info`, puis relancez la commande.

### L'exécution de scripts est désactivée (Windows)

- **Symptôme** : `.\scripts\init-db.ps1` échoue avec un message indiquant que l'exécution de
  scripts est désactivée sur ce système.
- **Cause probable** : la stratégie d'exécution PowerShell par défaut de Windows.
- **Solution** : dans la même fenêtre, lancez
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, puis relancez le script.

### Mot de passe refusé

- **Symptôme** : un script échoue avec `password authentication failed for user "postgres"` (ou
  `"immo_admin"`, ou `"analyst_ro"`).
- **Causes probables et solutions** :
  - `POSTGRES_PASSWORD` a été modifié dans `.env` **après** la première création de la base. Ce
    mot de passe est fixé une fois pour toutes à la création. Remettez l'ancienne valeur, ou
    repartez de zéro avec `docker compose down -v`, ce qui **supprime toutes les données** (voir
    l'étape 11).
  - `IMMO_ADMIN_PASSWORD` ou `ANALYST_RO_PASSWORD` a été modifié dans `.env`. Relancez
    `.\scripts\init-db.ps1`, qui réapplique ces deux mots de passe.
  - Le mot de passe contient des guillemets, des espaces, `$` ou `#`. Utilisez uniquement des
    lettres et des chiffres (voir l'étape 4), puis appliquez la solution correspondante
    ci-dessus.
- **Symptôme voisin** : `fe_sendauth: no password supplied` lors d'une commande `psql` tapée à la
  main. C'est normal après l'étape 6.3 : fournissez le mot de passe (`psql` le demande si vous
  n'ajoutez pas `-w`), ou passez par les scripts.

### Un fichier est absent de `data/raw`

- **Symptôme** : `load.ps1` s'arrête immédiatement avec `Fichier introuvable : data/raw/<nom>`.
- **Cause probable** : un fichier n'a pas été téléchargé, il porte un autre nom (par exemple
  `full-2025.csv` au lieu de `dvf_2025.csv`), ou le zip a été extrait dans un autre dossier que
  `data/raw/populations_reference_2023/`. Le script vérifie la présence des trois fichiers, même
  avec l'option `-Only`.
- **Solution** : reprenez l'étape 5 et contrôlez avec la commande de l'étape 5.4.

### Erreur de droits sur `COPY`

- **Symptôme** : `permission denied to COPY from a file`, avec le détail
  `Only roles with privileges of the "pg_read_server_files" role may COPY from a file.`
- **Causes probables** :
  - le SQL de chargement a été lancé à la main avec un autre rôle, par exemple `analyst_ro`,
    qui n'a volontairement pas ce droit ;
  - `init-db.ps1` n'a pas été exécuté jusqu'au bout : c'est `sql/01_roles.sql` qui donne ce
    droit à `immo_admin`.
- **Solution** : lancez `.\scripts\init-db.ps1`, puis `.\scripts\load.ps1`, qui se connecte en
  tant que `immo_admin`.
- **Erreur voisine** : `could not open file "/data/raw/...": No such file or directory`. Le
  fichier n'est pas visible dans le conteneur. Vérifiez qu'il est bien dans `data/raw/` du
  dossier `DataAgent`, et que `docker compose` est lancé depuis ce dossier.

### PostgreSQL a redémarré

- **Symptômes** : une commande échoue avec `the database system is in recovery mode`,
  `the database system is not yet accepting connections` ou
  `terminating connection due to administrator command`.
- **Causes possibles** : le conteneur a été redémarré, Docker Desktop manque de mémoire, ou un
  processus du serveur s'est arrêté. Après un arrêt anormal, PostgreSQL rejoue automatiquement
  son journal de transactions avant d'accepter à nouveau les connexions.
- **Solution** :
  1. Attendez la fin de la récupération : `docker compose logs db --tail 30` doit afficher
     `database system is ready to accept connections`.
  2. Les données déjà validées sont conservées. Un chargement interrompu est annulé en entier,
     car chaque fichier est chargé en une seule transaction.
  3. Relancez `.\scripts\verify.ps1` pour contrôler les compteurs.
  4. Si un chargement a été interrompu, relancez-le. Si les communes sont déjà chargées et que
     seul DVF manque, lancez `.\scripts\load.ps1 -Only dvf` (un `load.ps1` complet serait refusé
     par le garde-fou des communes).
  5. Si les journaux montrent `terminated by signal 9: Killed`, augmentez la mémoire allouée à
     Docker Desktop (Settings > Resources).

## 11. Désinstallation

Depuis le dossier `DataAgent` :

```powershell
docker compose down -v
```

Cette commande **supprime** :

- le conteneur `dataia_postgres` ;
- le réseau Docker du projet ;
- le **volume de données** (nommé d'après le dossier, par exemple `dataagent_pgdata`). Il
  contient toute la base : tables chargées, vue, rôles, mots de passe, et modification de
  `pg_hba.conf` de l'étape 6.3. **Cette suppression est définitive.**

Elle **ne supprime pas** :

- le dossier du projet, y compris `.env` et les fichiers téléchargés dans `data/raw/` (environ
  850 Mo) ;
- l'image Docker `postgres:16`, que vous pouvez supprimer avec `docker image rm postgres:16` si
  aucun autre projet ne l'utilise.

Pour tout effacer, supprimez ensuite le dossier `DataAgent`.
