# Initialise la base : extension, rôles et schémas, tables, vues.
# Idempotent : n'efface aucune donnée existante.
# Usage : .\scripts\init-db.ps1

. (Join-Path $PSScriptRoot '_common.ps1')

docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up a echoue." }
Wait-Database

# Superutilisateur technique : extension, rôles, schémas
Invoke-SqlFile '/sql/00_extensions.sql'
Invoke-SqlFile '/sql/01_roles.sql'

# immo_admin (non superutilisateur) : objets du schéma immo
Invoke-SqlFile '/sql/02_schema.sql' -User 'immo_admin'
Invoke-SqlFile '/sql/03_views.sql'  -User 'immo_admin'

Write-Host "Initialisation terminee." -ForegroundColor Green
