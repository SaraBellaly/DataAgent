# Rôles et sécurité

## Rôles

| Rôle | Attributs | Usage | Droits |
|------|-----------|-------|--------|
| `postgres` (`POSTGRES_USER`) | SUPERUSER (compte d'initialisation, non modifiable) | Création de l'extension, des rôles et des schémas : `sql/00_extensions.sql`, `sql/01_roles.sql` | Tous |
| `immo_admin` | LOGIN, **NOSUPERUSER**, NOCREATEDB, NOCREATEROLE | Création des tables et chargement des données : `sql/02_schema.sql`, `sql/03_views.sql`, `sql/load/*` | Propriétaire des schémas `immo` et `immo_staging` ; membre de **`pg_read_server_files`** |
| `analyst_ro` | LOGIN, NOSUPERUSER | Rôle de l'agent | `SELECT` sur `immo` uniquement (droits par défaut `FOR ROLE immo_admin`) ; rien sur `immo_staging` ; membre de `pg_read_all_stats` ; `statement_timeout = 30s`, `default_transaction_read_only = on` |

Pourquoi un superutilisateur séparé : PostgreSQL interdit de retirer l'attribut SUPERUSER au
compte d'initialisation du cluster (`The bootstrap user must have the SUPERUSER attribute`).
Ce compte est donc réservé à l'administration, et le travail courant se fait avec `immo_admin`.

Les mots de passe sont dans `.env` (non versionné) et ne sont jamais écrits dans le code :
`sql/01_roles.sql` les lit avec `\getenv` dans l'environnement du conteneur.

## `pg_read_server_files` reste un droit sensible

`immo_admin` en a besoin pour `COPY … FROM '/data/raw/…'` : un `COPY` depuis un fichier lu par le
serveur est réservé aux superutilisateurs et aux membres de ce rôle.

Ce droit est plus restreint que SUPERUSER, mais il reste puissant :

- il permet de lire **n'importe quel fichier accessible à l'utilisateur système `postgres` du
  conteneur**, pas seulement `data/raw`. Cela inclut le répertoire de données du cluster
  (`/var/lib/postgresql/data`, et donc `pg_hba.conf`, `postgresql.conf` et les fichiers des tables)
  et les fichiers montés (`/sql`, `/data/raw`) ;
- il donne aussi accès aux fonctions `pg_read_file()`, `pg_read_binary_file()` et `pg_ls_dir()`.

Mesures en place :

- `analyst_ro` (le rôle de l'agent) **n'est pas** membre de `pg_read_server_files` ;
- `data/raw` et `sql` sont montés **en lecture seule** dans le conteneur ;
- le port n'est exposé que sur `127.0.0.1` ;
- le mot de passe de `immo_admin` n'est utilisé que par les scripts de chargement.

Pistes si le projet sort du cadre local :

- charger avec `\copy` (lecture côté client par psql) au lieu de `COPY … FROM 'fichier'`, ce
  qui supprime le besoin de `pg_read_server_files` ;
- ou n'accorder ce rôle que le temps du chargement (`GRANT` / `REVOKE` autour de `scripts/load.ps1`).

## Authentification : mot de passe exigé partout (`scram-sha-256`)

Par défaut, l'image officielle `postgres` met les connexions locales en `trust` (sans mot de
passe) : socket Unix, `127.0.0.1` et `::1` à l'intérieur du conteneur. Le 2026-11-13, ces règles
ont été passées en `scram-sha-256`, sans recréer le volume. Toute connexion exige donc un mot de
passe.

| Origine de la connexion | Méthode |
|---|---|
| Socket Unix, dans le conteneur | `scram-sha-256` |
| TCP `127.0.0.1` / `::1`, dans le conteneur | `scram-sha-256` |
| Réplication (locale, `127.0.0.1`, `::1`) | `scram-sha-256` |
| Toute autre adresse : autre conteneur, hôte via le port publié | `scram-sha-256` |

### Ce qui a été fait

1. Vérification préalable : les trois rôles (`postgres`, `immo_admin`, `analyst_ro`) ont un mot
   de passe stocké en SCRAM (`pg_authid.rolpassword` commence par `SCRAM-SHA-256$`). Sans cela,
   on aurait été bloqué hors de la base.
2. Sauvegarde : `/var/lib/postgresql/data/pg_hba.conf.bak_trust`, dans le volume.
3. Remplacement de `trust` par `scram-sha-256` sur les lignes actives de
   `/var/lib/postgresql/data/pg_hba.conf`, avec une session `postgres` restée ouverte pendant
   la modification.
4. `SELECT pg_reload_conf();`, puis contrôle avec `pg_hba_file_rules` (colonne `error` vide).

### Vérifications

- Sans mot de passe (`psql -w`), par socket et par `127.0.0.1`, pour les trois rôles :
  `fe_sendauth: no password supplied`.
- Mauvais mot de passe, pour les trois rôles : `password authentication failed`.
- Bons mots de passe de `.env` : connexion acceptée par socket, `127.0.0.1` et `::1`.
- `scripts/init-db.ps1` : OK (code 0). `scripts/load.ps1 -DryRun` : connexion `immo_admin`
  et `COPY` OK, puis refus attendu des garde-fous (données déjà chargées).
- Depuis un autre conteneur du réseau du projet : un mauvais mot de passe est refusé. Les
  connexions depuis l'hôte (port publié) passent par la même règle `scram-sha-256`, mais n'ont
  pas été testées directement (psql n'est pas installé sur l'hôte).

### Comment les scripts fournissent le mot de passe

`scripts/_common.ps1` lit `.env`, choisit le mot de passe du rôle utilisé et le place dans la
variable d'environnement `PGPASSWORD` du processus PowerShell, le temps de l'appel. Il la transmet
ensuite à `docker compose exec -e PGPASSWORD` (nom de la variable seulement, sans valeur sur la
ligne de commande). Le mot de passe n'apparaît donc ni dans les scripts ni dans la liste des
processus de l'hôte.

### Revenir en arrière

```sh
docker compose exec -u postgres db cp /var/lib/postgresql/data/pg_hba.conf.bak_trust /var/lib/postgresql/data/pg_hba.conf
# puis, en tant que postgres : SELECT pg_reload_conf();
```

### Limites

- La modification est dans le volume (`pg_hba.conf` du répertoire de données), pas dans le dépôt.
  Si le volume est recréé (`docker compose down -v`), l'image repart avec les règles `trust` :
  il faudra refaire la modification, ou passer
  `POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256 --auth-host=scram-sha-256` à la création.
- Un accès root au conteneur (`docker compose exec -u root db …`) permet toujours de modifier
  `pg_hba.conf` : l'accès à Docker reste un accès administrateur.

## Incident du 2026-11-13 : redémarrage de PostgreSQL (récupération automatique)

Pendant la modification de `pg_hba.conf`, une session `postgres` de secours avait été ouverte
en arrière-plan dans le conteneur (`docker compose exec -d …`). Dans l'image officielle, le
postmaster de PostgreSQL tourne avec le PID 1 et récupère les processus orphelins. En arrêtant cette
session avec `pkill`, un processus rattaché au postmaster (PID 6322) a reçu le signal 15.
Le postmaster a interprété sa disparition comme un plantage : il a arrêté toutes les connexions
et lancé une récupération automatique, avec 49 s de rejeu du journal de transactions (WAL).

Constat après récupération :
- Aucune donnée perdue : 34 920 lignes INSEE et 3 793 113 lignes DVF. La lecture séquentielle
  complète et la lecture par l'index `code_commune` donnent le même nombre de lignes et la même
  empreinte. Les index de clé primaire sont cohérents.
- Les tables `UNLOGGED` de `immo_staging` sont vidées par la récupération ; elles étaient vides.
- Les statistiques de `pg_stat_statements` ont été remises à zéro.

À retenir : ne pas lancer de processus en arrière-plan dans le conteneur `db` (ni
`docker compose exec -d`, ni `&`), ou ajouter `init: true` au service dans
`docker-compose.yml`, pour qu'un vrai processus init récupère les orphelins.
