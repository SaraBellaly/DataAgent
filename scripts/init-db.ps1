# Initialise la base : extension, rôles et schémas, tables, vues.
# Idempotent : n'efface aucune donnée existante.
# Usage : .\scripts\init-db.ps1

. (Join-Path $PSScriptRoot '_common.ps1')

# Base seule : l'application (service backend) se lance après l'initialisation
docker compose up -d db
if ($LASTEXITCODE -ne 0) { throw "docker compose up a echoue." }
Wait-Database

# Superutilisateur technique : extension, rôles, schémas
Invoke-SqlFile '/sql/00_extensions.sql'
Invoke-SqlFile '/sql/01_roles.sql'

# immo_admin (non superutilisateur) : objets du schéma immo
Invoke-SqlFile '/sql/02_schema.sql' -User 'immo_admin'
Invoke-SqlFile '/sql/03_views.sql'  -User 'immo_admin'

# immo_admin : tables de l'application (comptes, sessions, historique), droits de app_agent
Invoke-SqlFile '/sql/06_app_schema.sql' -User 'immo_admin'

Write-Host "Initialisation terminee." -ForegroundColor Green
