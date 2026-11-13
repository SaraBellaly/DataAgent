# Fonctions partagées par les scripts du projet.
# psql s'exécute DANS le conteneur : aucune installation locale requise.
# Les identifiants viennent de .env, jamais des scripts. Le mot de passe est transmis à psql
# par la variable d'environnement PGPASSWORD (docker compose exec -e PGPASSWORD, sans valeur
# sur la ligne de commande), car pg_hba exige scram-sha-256 même pour les connexions locales.

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$EnvFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $EnvFile)) {
    throw "Fichier .env introuvable. Copiez .env.example en .env et renseignez les valeurs."
}

# Lecture de .env (lignes CLE=valeur, commentaires # ignorés)
$DotEnv = @{}
foreach ($line in [IO.File]::ReadAllLines($EnvFile, [Text.Encoding]::UTF8)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') { $DotEnv[$Matches[1]] = $Matches[2] }
}

function Get-RolePassword {
    # Mot de passe du rôle PostgreSQL, lu dans .env
    param([Parameter(Mandatory)][string]$User)
    $key = switch ($User) {
        $DotEnv['POSTGRES_USER'] { 'POSTGRES_PASSWORD' }
        'immo_admin'             { 'IMMO_ADMIN_PASSWORD' }
        'analyst_ro'             { 'ANALYST_RO_PASSWORD' }
        default                  { throw "Role inconnu : $User" }
    }
    if (-not $DotEnv[$key]) { throw "$key absent de .env" }
    return $DotEnv[$key]
}

function Invoke-Psql {
    # Lance psql dans le conteneur sous le rôle $User, avec son mot de passe (PGPASSWORD).
    # $InputText : SQL envoyé sur l'entrée standard (optionnel).
    param([string]$User, [string[]]$PsqlArgs = @(), [string]$InputText)
    if (-not $User) { $User = $DotEnv['POSTGRES_USER'] }
    $env:PGPASSWORD = Get-RolePassword $User
    try {
        $cmd = @('compose', 'exec', '-T', '-e', 'PGPASSWORD', 'db', 'psql', '-X', '-U', $User) + $PsqlArgs
        # Out-Host : la sortie de psql s'affiche sans polluer la valeur de retour (code de sortie)
        if ($PSBoundParameters.ContainsKey('InputText')) { $InputText | & docker @cmd | Out-Host }
        else { & docker @cmd | Out-Host }
        return $LASTEXITCODE
    }
    finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
}

function Invoke-SqlFile {
    # Exécute un fichier SQL monté dans le conteneur (/sql/...). Arrêt à la première erreur.
    # $Vars : variables psql optionnelles, ex. @{ dvf_file = '/data/raw/dvf_2024.csv' }
    # -SingleTransaction : tout le fichier dans une transaction (psql -1), tout ou rien.
    # -User : rôle de connexion (défaut : superutilisateur technique POSTGRES_USER).
    param([Parameter(Mandatory)][string]$ContainerPath, [hashtable]$Vars = @{},
          [switch]$SingleTransaction, [string]$User)
    Write-Host ">> $ContainerPath$(if ($User) { " (en tant que $User)" })" -ForegroundColor Cyan
    $a = @('-v', 'ON_ERROR_STOP=1')
    foreach ($k in $Vars.Keys) { $a += @('-v', "$k=$($Vars[$k])") }
    if ($SingleTransaction) { $a += '--single-transaction' }
    $a += @('-f', $ContainerPath)
    $code = Invoke-Psql -User $User -PsqlArgs $a
    if ($code -ne 0) { throw "Echec de $ContainerPath (code $code)" }
}

function Wait-Database {
    # Attend que le serveur accepte les connexions (pg_isready ne s'authentifie pas).
    for ($i = 0; $i -lt 60; $i++) {
        docker compose exec -T db pg_isready -q 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    }
    throw "PostgreSQL ne repond pas. Verifiez 'docker compose ps' et 'docker compose logs db'."
}
