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
$composeFiles = @('-f', 'compose.yaml', '-f', 'compose.demo.yaml', '-f', 'compose.ai.yaml')
Write-Host 'Starting local AI. First download is approximately 4.7 GB; keep this window open.'
docker compose @composeFiles up -d --wait ollama
if ($LASTEXITCODE -ne 0) { throw 'Ollama container did not start.' }
docker compose @composeFiles exec -T ollama ollama pull qwen2.5:7b
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Check Docker memory, disk space, and internet connection.' }
docker compose @composeFiles up --build -d --force-recreate --wait --wait-timeout 900
if ($LASTEXITCODE -ne 0) { docker compose @composeFiles logs --tail=80 api ollama; throw 'App with AI failed to start.' }
docker compose @composeFiles exec -T ollama ollama run qwen2.5:7b 'Reply with one word: ready'
if ($LASTEXITCODE -ne 0) { throw 'Model failed to load. Increase Docker memory or use start-demo.bat.' }
$probe = Invoke-RestMethod -Uri 'http://localhost:8080/api/v1/search/natural' -Method Post -ContentType 'application/json' -Body '{"text":"\u043c\u0443\u0437\u0435\u0439", "city":"msk"}' -TimeoutSec 70
if ($probe.llm_status -eq 'ok') { Write-Host 'AI verified: the model returned a valid search intent.' }
else { Write-Warning 'The app is running with local parsing. AI timed out or returned invalid data; check docker compose logs ollama.' }
Start-Process 'http://localhost:8080'
