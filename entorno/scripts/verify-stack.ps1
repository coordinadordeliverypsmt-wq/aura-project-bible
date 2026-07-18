# Verificacion del stack de AURA en Windows (acta D24).
$fail = 0
function Ok($m){ Write-Host "  [ OK ] $m" }
function Bad($m){ Write-Host "  [FAIL] $m"; $script:fail = 1 }
Write-Host "==> Verificacion del stack de AURA (Windows)"
$py = "$PSScriptRoot\..\.venv\Scripts\python.exe"; if (-not (Test-Path $py)) { $py = "python" }
foreach ($m in @("nats","faster_whisper","qdrant_client")) {
  & $py -c "import $m" 2>$null; if ($LASTEXITCODE -eq 0) { Ok "python: $m" } else { Bad "python: $m NO importable" }
}
if (Get-Command ollama -ErrorAction SilentlyContinue) { Ok "ollama instalado" } else { Bad "ollama no instalado" }
try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null; Ok "Ollama responde :11434" } catch { Bad "Ollama no responde (ollama serve)" }
try { $c = New-Object Net.Sockets.TcpClient("127.0.0.1",4222); $c.Close(); Ok "NATS :4222" } catch { Write-Host "  [WARN] NATS no corriendo (nats-server -p 4222)" }
Write-Host "==> RESULTADO: $(if ($fail -eq 0){'STACK OPERATIVO'} else {'FALTAN COMPONENTES'})"
exit $fail
