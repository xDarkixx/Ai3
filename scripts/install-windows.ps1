$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host '[1/5] Prüfe Docker Desktop ...'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw 'Docker Desktop ist nicht installiert. Installiere Docker Desktop und starte es, danach diesen Installer erneut ausführen.'
}
docker compose version | Out-Host
docker info | Out-Null

Write-Host '[2/5] Erstelle sichere .env, falls noch nicht vorhanden ...'
if (-not (Test-Path '.env')) {
  $AdminKey = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 })) -replace '[+/=]',''
  $AdminPassword = 'AI3-' + [Convert]::ToBase64String((1..18 | ForEach-Object { Get-Random -Maximum 256 })) -replace '[+/=]',''
  @"
AI3_ADMIN_KEY=$AdminKey
AI3_ADMIN_PASSWORD=$AdminPassword
AI3_ADMIN_SESSION_HOURS=12
AI3_MODEL=llama3.2:3b
AI3_OLLAMA_URL=http://ollama:11434
AI3_LLM_BASE_URL=http://ollama:11434/v1
AI3_LLM_API_KEY=
AI3_LLM_TIMEOUT=300
AI3_VLLM_URL=
AI3_LLAMACPP_URL=
AI3_BACKEND=ollama
AI3_ENABLE_ADVANCED_SECURITY=1
AI3_ACCESS_TOKEN_MINUTES=15
AI3_REFRESH_TOKEN_DAYS=30
AI3_RATE_LIMIT_RPM=120
AI3_DAILY_REQUEST_LIMIT=0
AI3_BACKUP_DIR=/data/backups
"@ | Set-Content -Encoding utf8 '.env'
  Write-Host "Admin-Passwort (einmalig anzeigen): $AdminPassword"
}

$envLines = Get-Content '.env'
$AdminKey = ($envLines | Where-Object { $_ -like 'AI3_ADMIN_KEY=*' }) -replace '^AI3_ADMIN_KEY=',''
$Model = ($envLines | Where-Object { $_ -like 'AI3_MODEL=*' }) -replace '^AI3_MODEL=',''

Write-Host '[3/5] Starte AI3 + Ollama + lokales Modell ...'
docker compose up -d --build

Write-Host '[4/5] Warte auf AI3 ...'
$ok = $false
1..90 | ForEach-Object {
  if (-not $ok) {
    try { Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8080/health' -TimeoutSec 3 | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 2 }
  }
}
if (-not $ok) { docker compose logs --tail=120; throw 'AI3 wurde nicht rechtzeitig erreichbar.' }

$headers = @{ 'X-AI3-Admin-Key' = $AdminKey; 'Content-Type' = 'application/json' }
try { Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/v1/principals' -Headers $headers -Body '{"name":"assistant-01","kind":"agent"}' | Out-Null } catch {}
$tokenBody = '{"principal":"assistant-01","name":"local","scopes":["ai:inference","agents:read"]}'
$token = (Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/v1/tokens' -Headers $headers -Body $tokenBody).token

New-Item -ItemType Directory -Force 'openclaw' | Out-Null
@"
{
  models: {
    mode: "merge",
    providers: {
      ai3: {
        baseUrl: "http://127.0.0.1:8080/v1",
        apiKey: "$token",
        api: "openai-completions",
        timeoutSeconds: 300,
        models: [{ id: "$Model", name: "AI3 Local $Model", reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 32768, maxTokens: 8192 }]
      }
    }
  },
  agents: { defaults: { model: { primary: "ai3/$Model" } } }
}
"@ | Set-Content -Encoding utf8 'openclaw/ai3-provider.generated.json5'

Write-Host '[5/5] Installation fertig.'
Write-Host 'AI3: http://localhost:8080'
Write-Host "Modell: $Model"
Write-Host 'OpenClaw: openclaw/ai3-provider.generated.json5'
Write-Host 'Token wurde erzeugt und nicht ins Repository geschrieben.'
