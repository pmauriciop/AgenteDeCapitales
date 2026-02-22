# push_to_github.ps1
# ──────────────────────────────────────────────────────────
# Ejecutar desde la carpeta del proyecto:
#   .\push_to_github.ps1
# ──────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$repo = "https://github.com/pmauriciop/AgenteDeCapitales.git"

Write-Host "`n🔧 Configurando git..." -ForegroundColor Cyan

git init
git remote remove origin 2>$null
git remote add origin $repo

Write-Host "`n📋 Archivos a commitear:" -ForegroundColor Cyan
git add .
git status --short

Write-Host "`n💾 Creando commit..." -ForegroundColor Cyan
git commit -m "feat: implementacion completa del MVP

- database/: cliente Supabase, modelos y repositorios con encriptacion Fernet
- ai/: NLP (GPT-4o), Whisper STT, OCR Vision, parser de PDFs
- services/: TransactionService, BudgetService, RecurringService
- bot/: app + handlers (texto, voz, foto, PDF, conversaciones)
- reports/: generador de reportes PDF con graficos (ReportLab + Matplotlib)
- tests/: 46 tests unitarios (todos pasan)
- supabase/migrations/: schema SQL inicial
- pytest.ini, .gitignore, requirements.txt completo"

Write-Host "`n🚀 Enviando a GitHub..." -ForegroundColor Cyan
git branch -M main
git push -u origin main --force

Write-Host "`n✅ Push exitoso a $repo" -ForegroundColor Green
