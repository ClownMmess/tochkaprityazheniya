$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and start Docker Desktop first.' }
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running.' }
if (-not (Test-Path '.env')) {
    function New-LocalSecret {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLower()
    }
    $password = New-LocalSecret
    $session = New-LocalSecret
    $webhook = New-LocalSecret
    $content = [IO.File]::ReadAllText((Join-Path (Get-Location) '.env.example'))
    $content = $content.Replace('local_dev_only', $password)
    $content = $content -replace '(?m)^SESSION_SECRET=.*$', "SESSION_SECRET=$session"
    $content = $content -replace '(?m)^MAX_WEBHOOK_SECRET=.*$', "MAX_WEBHOOK_SECRET=$webhook"
    [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $content, (New-Object Text.UTF8Encoding($false)))
}
docker compose -f compose.yaml -f compose.demo.yaml up --build -d --force-recreate --wait --wait-timeout 900
if ($LASTEXITCODE -ne 0) {
    docker compose logs --no-color --tail=80 api
    throw 'Startup failed. Check: docker compose ps and docker compose logs api catalog worker frontend'
}
$version = Invoke-RestMethod 'http://localhost:8080/api/v1/runtime'
$uiVersion = Invoke-RestMethod 'http://localhost:8080/version.json'
if ($version.catalog_version -ne '1.3.2' -or $uiVersion.version -ne '1.3.2') { throw 'Version mismatch. Replace all files from the new ZIP and run start-demo again.' }
Start-Process 'http://localhost:8080'
Write-Host 'App: http://localhost:8080 . Demo users are available in the page header.'
