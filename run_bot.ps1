# run_bot.ps1
# ─────────────────────────────────────────────────────────────
# Watchdog: lanza el bot y lo reinicia automáticamente si cae.
#
# Uso:
#   .\run_bot.ps1
#
# Para correrlo minimizado al inicio de Windows, crear una tarea
# en el Programador de tareas apuntando a este script con:
#   powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\...\run_bot.ps1"
# ─────────────────────────────────────────────────────────────

$PYTHON   = "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
$SCRIPT   = "main.py"
$WORKDIR  = "C:\Users\Usuario\AgenteDeCapitales"
$MAX_RESTARTS   = 10     # reintentos máximos antes de rendirse
$RESTART_DELAY  = 5      # segundos de espera entre reinicios
$RESET_AFTER    = 300    # reiniciar el contador si estuvo vivo más de este tiempo (segundos)

Set-Location $WORKDIR
$env:PYTHONUTF8 = "1"

$restarts = 0

Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | INFO  | watchdog | Iniciando bot..." -ForegroundColor Cyan

while ($true) {
    $startTime = Get-Date

    # Lanzar el bot
    & $PYTHON -X utf8 $SCRIPT

    $exitCode  = $LASTEXITCODE
    $elapsed   = (Get-Date) - $startTime

    # Si estuvo corriendo mucho tiempo, resetear el contador de reinicios
    if ($elapsed.TotalSeconds -gt $RESET_AFTER) {
        $restarts = 0
    }

    $restarts++

    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | WARN  | watchdog | Bot detenido (exit=$exitCode, uptime=$([int]$elapsed.TotalSeconds)s, restart=$restarts/$MAX_RESTARTS)" -ForegroundColor Yellow

    if ($restarts -ge $MAX_RESTARTS) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | ERROR | watchdog | Demasiados reinicios. Abortando." -ForegroundColor Red
        break
    }

    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | INFO  | watchdog | Reiniciando en $RESTART_DELAY s..." -ForegroundColor Cyan
    Start-Sleep -Seconds $RESTART_DELAY
}
