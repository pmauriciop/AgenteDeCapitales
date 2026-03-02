# 🤖 Agente de Capitales

Bot de Telegram para gestión de finanzas personales con inteligencia artificial.  
Registrá gastos e ingresos por texto, voz, foto de ticket o resumen PDF bancario. Analizá tu dinero con IA.

---

## ✨ Características

| Feature | Detalle |
|---|---|
| 💬 Texto libre | "Gasté $500 en el super" → se guarda solo |
| 🎤 Mensajes de voz | Transcripción automática con Whisper (Groq) |
| 📷 Foto de tickets | Extracción de datos con visión IA (Groq, privacy-first) |
| 📄 PDF bancario | Importación de resúmenes de tarjeta con detección de cuotas |
| 📊 Resumen mensual | Balance, gastos por categoría, consejo con IA |
| 💼 Presupuestos | Límites por categoría con alertas al 80% y 100% |
| 🔁 Recurrentes | Suscripciones y pagos automáticos periódicos |
| � Analista IA | Preguntas en lenguaje natural sobre tus finanzas |
| 🌐 Dashboard web | Panel visual con gráficos (FastAPI + React) |
| 🔐 Encriptación | Descripciones cifradas con Fernet (AES-128) antes de la DB |
| 🛡️ Privacy-first | Datos sensibles sanitizados antes de enviarse al LLM externo |

---

## 🏗️ Arquitectura

```
AgenteDeCapitales/
├── main.py                   # Punto de entrada + logging rotativo
├── run_bot.ps1               # Watchdog de producción (PowerShell)
├── config.py                 # Variables de entorno (centralizado)
├── requirements.txt
├── .env.example
│
├── ai/                       # Inteligencia Artificial
│   ├── nlp.py                # Clasificación de intenciones + parseo de transacciones
│   ├── transcriber.py        # Whisper STT (voz → texto) — Groq
│   ├── ocr.py                # Visión IA (foto → datos financieros, 2 pasos, privacy-first)
│   ├── pdf_parser.py         # Importación de resúmenes bancarios PDF
│   └── analyst.py            # Análisis financiero en lenguaje natural
│
├── bot/                      # Bot de Telegram
│   ├── app.py                # Configuración y registro de handlers
│   ├── keyboards.py          # Teclados inline y reply
│   ├── states.py             # Estados de ConversationHandlers
│   └── handlers/
│       ├── start.py          # /start, /ayuda
│       ├── messages.py       # Texto libre con NLP
│       ├── voice.py          # Mensajes de voz
│       ├── photo.py          # Fotos de tickets
│       ├── pdf_import.py     # Importación de PDFs bancarios
│       ├── analyst_handler.py# /analizar — preguntas a la IA
│       ├── expense.py        # Registro manual de gastos
│       ├── income.py         # Registro manual de ingresos
│       ├── summary.py        # Resumen mensual + consejo IA
│       ├── budget.py         # Gestión de presupuestos
│       ├── recurring.py      # Transacciones recurrentes
│       ├── report.py         # Generación de PDF
│       └── callbacks.py      # Callbacks genéricos
│
├── database/                 # Capa de datos
│   ├── client.py             # Cliente Supabase (singleton)
│   ├── encryption.py         # Cifrado Fernet
│   ├── models.py             # Dataclasses (User, Transaction, Budget, Recurring)
│   └── repositories.py      # CRUD con Supabase
│
├── services/                 # Lógica de negocio
│   ├── transaction_service.py
│   ├── budget_service.py
│   ├── recurring_service.py
│   └── analyst_service.py    # Contexto + llamada al analista IA
│
├── dashboard_api.py          # API REST (FastAPI) para el dashboard web
├── dashboard/                # Frontend (Vite + React)
│
├── reports/                  # Generación de reportes
│   └── pdf_generator.py      # PDF con ReportLab + Matplotlib
│
└── tests/                    # 59/59 tests ✅
    ├── conftest.py
    ├── test_encryption.py
    ├── test_models.py
    ├── test_nlp.py
    ├── test_sanitizers.py
    ├── test_transaction_service.py
    ├── test_budget_service.py
    └── test_recurring_service.py
```

---

## 🚀 Instalación

### 1. Clonar y crear entorno

```bash
git clone <repo>
cd AgenteDeCapitales
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
```

Editar `.env`:

```env
TELEGRAM_BOT_TOKEN=tu_token_aqui

# LLM principal (obligatorio)
GROQ_API_KEY=tu_clave_groq_aqui
GROQ_MODEL=llama-3.3-70b-versatile

# Requerido por config.py pero no se usa activamente
OPENAI_API_KEY=sk-dummy

SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=tu_clave_aqui
ENCRYPTION_KEY=tu_clave_fernet_aqui
ENV=production
LOG_LEVEL=INFO
```

> ⚠️ **Importante**: si perdés `ENCRYPTION_KEY`, los datos cifrados en la DB son **irrecuperables**. Guardala en un gestor de contraseñas.

Generar `ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Configurar Supabase

Ejecutar en el SQL Editor de Supabase:

```sql
-- Usuarios
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_id BIGINT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Transacciones
CREATE TABLE transactions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID REFERENCES users(id) ON DELETE CASCADE,
  amount                NUMERIC(12, 2) NOT NULL,
  category              TEXT NOT NULL,
  description           TEXT,
  type                  TEXT CHECK (type IN ('income', 'expense')) NOT NULL,
  date                  DATE NOT NULL,
  installment_current   INT,          -- cuota actual (ej: 3)
  installment_total     INT,          -- total de cuotas (ej: 12)
  installments_remaining INT,         -- cuotas restantes
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Presupuestos
CREATE TABLE budgets (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
  category     TEXT NOT NULL,
  limit_amount NUMERIC(12, 2) NOT NULL,
  month        TEXT NOT NULL,             -- "YYYY-MM"
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, category, month)
);

-- Recurrentes
CREATE TABLE recurring (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  amount      NUMERIC(12, 2) NOT NULL,
  category    TEXT NOT NULL,
  description TEXT,
  frequency   TEXT CHECK (frequency IN ('daily','weekly','monthly','yearly')) NOT NULL,
  next_date   DATE NOT NULL,
  active      BOOLEAN DEFAULT TRUE
);

-- Índices de performance
CREATE INDEX idx_transactions_user_date ON transactions(user_id, date);
CREATE INDEX idx_budgets_user_month ON budgets(user_id, month);
CREATE INDEX idx_recurring_user_active ON recurring(user_id, active);
```

### 4. Ejecutar

**Modo desarrollo** (sin watchdog):
```powershell
python -X utf8 main.py
```

**Modo producción** (con watchdog — reinicio automático ante crashes):
```powershell
.\run_bot.ps1
```
El watchdog reinicia el bot automáticamente hasta 10 veces. Si el bot vivió más de 5 minutos, el contador se resetea.

**Dashboard web** (opcional, en terminales separadas):
```powershell
# Terminal 1 — API
python dashboard_api.py

# Terminal 2 — Frontend
cd dashboard
npm install   # solo la primera vez
npm run dev
```
Abre `http://localhost:5173` en el navegador.

---

## 🧪 Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

**59/59 passing** ✅

| Archivo | Qué cubre |
|---|---|
| `test_encryption.py` | Cifrado/descifrado Fernet, claves inválidas |
| `test_models.py` | Dataclasses, validaciones, serialización |
| `test_nlp.py` | Parseo de intenciones, clasificación de transacciones |
| `test_sanitizers.py` | Sanitización de CUIT, CBU, tarjetas, email, DNI (12 casos) |
| `test_transaction_service.py` | CRUD, deduplicación, add_from_parsed |
| `test_budget_service.py` | Límites, alertas 80%/100%, consulta mensual |
| `test_recurring_service.py` | Frecuencias, próxima fecha, activación/desactivación |

---

## 💬 Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Bienvenida y menú principal |
| `/resumen` | Resumen financiero del mes |
| `/reporte` | Generar PDF (también: `/reporte 2026-01`) |
| `/analizar` | Hacerle una pregunta al analista IA |
| `/gasto` | Registrar gasto paso a paso |
| `/ingreso` | Registrar ingreso paso a paso |
| `/presupuesto` | Ver estado de presupuestos |
| `/presupuesto_nuevo` | Definir presupuesto para una categoría |
| `/recurrentes` | Ver recurrentes activas |
| `/recurrente_nuevo` | Crear nueva recurrente |
| `/ayuda` | Lista de comandos |

También podés enviar directamente:
- **Texto libre**: "Gasté $1200 en almuerzo" → se registra solo
- **Audio**: el bot transcribe y procesa automáticamente
- **Foto de ticket**: extracción IA de monto, comercio y categoría
- **PDF bancario**: importación de resumen con detección de cuotas

---

## 🔒 Seguridad y privacidad

- Las descripciones de transacciones se almacenan **cifradas** (Fernet AES-128) antes de llegar a la DB.
- **Sanitización antes de cada llamada LLM externa**: CUIT, CBU, número de tarjeta, email, DNI, nombre titular y domicilio son removidos del texto antes de enviarlo a Groq.
- OCR en **2 pasos**: paso 1 extrae texto crudo (única llamada con imagen), paso 2 parsea el texto ya sanitizado (sin imagen, sin PII).
- Los logs de voz registran solo el largo del audio, no la transcripción.
- Nunca subir `.env` a Git (está en `.gitignore`).
- Usar Row Level Security (RLS) en Supabase en producción.

## 📋 Logs

Los logs rotan automáticamente:
- Archivo activo: `bot.log`
- Backups: `bot.log.1`, `bot.log.2`, `bot.log.3`
- Tamaño máximo por archivo: **5 MB** → total máximo en disco: **~20 MB**

## 🗺️ Roadmap

### Alta prioridad
- [ ] Tests para `database/repositories.py` (mock Supabase)
- [ ] Tests para `ai/pdf_parser.py` (extracción estructurada)
- [ ] Tests para `services/analyst_service.py`
- [ ] Tests para endpoints de `dashboard_api.py`

### Features
- [ ] Notificaciones proactivas (alertas programadas)
- [ ] Metas de ahorro
- [ ] Múltiples monedas
- [ ] Exportar a Excel
- [ ] Deploy en Railway / Render con variables de entorno seguras
