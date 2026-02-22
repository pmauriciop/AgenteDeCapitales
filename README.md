# 🤖 Agente de Capitales

Bot de Telegram para gestión de finanzas personales con inteligencia artificial.  
Registrá gastos e ingresos por texto, voz o foto de ticket. Analizá tu dinero con IA.

---

## ✨ Características

| Feature | Detalle |
|---|---|
| 💬 Texto libre | "Gasté $500 en el super" → se guarda solo |
| 🎤 Mensajes de voz | Transcripción automática con Whisper |
| 📷 Foto de tickets | Extracción de datos con GPT-4o Vision |
| 📊 Resumen mensual | Balance, gastos por categoría, consejo con IA |
| 💼 Presupuestos | Límites por categoría con alertas al 80% y 100% |
| 🔁 Recurrentes | Suscripciones y pagos automáticos periódicos |
| 📄 Reporte PDF | Reporte mensual completo con gráficos |
| 🔐 Encriptación | Datos sensibles cifrados con Fernet (AES-128) |

---

## 🏗️ Arquitectura

```
AgenteDeCapitales/
├── main.py                   # Punto de entrada
├── config.py                 # Variables de entorno (centralizado)
├── requirements.txt
├── .env.example
│
├── ai/                       # Inteligencia Artificial
│   ├── nlp.py                # Clasificación de intenciones + parseo de transacciones
│   ├── transcriber.py        # Whisper STT (voz → texto)
│   └── ocr.py                # GPT-4o Vision (foto → datos financieros)
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
│   └── recurring_service.py
│
├── reports/                  # Generación de reportes
│   └── pdf_generator.py      # PDF con ReportLab + Matplotlib
│
└── tests/
    ├── test_encryption.py
    ├── test_models.py
    ├── test_transaction_service.py
    └── test_budget_service.py
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
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=tu_clave_aqui
ENCRYPTION_KEY=tu_clave_fernet_aqui
ENV=development
LOG_LEVEL=INFO
```

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
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  amount      NUMERIC(12, 2) NOT NULL,
  category    TEXT NOT NULL,
  description TEXT,
  type        TEXT CHECK (type IN ('income', 'expense')) NOT NULL,
  date        DATE NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW()
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

```bash
python main.py
```

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 💬 Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Bienvenida y menú principal |
| `/resumen` | Resumen financiero del mes |
| `/reporte` | Generar PDF (también: `/reporte 2026-01`) |
| `/gasto` | Registrar gasto paso a paso |
| `/ingreso` | Registrar ingreso paso a paso |
| `/presupuesto` | Ver estado de presupuestos |
| `/presupuesto_nuevo` | Definir presupuesto para una categoría |
| `/recurrentes` | Ver recurrentes activas |
| `/recurrente_nuevo` | Crear nueva recurrente |
| `/ayuda` | Lista de comandos |

---

## 🔒 Seguridad

- Las descripciones de transacciones se almacenan **cifradas** (Fernet AES-128).
- Nunca subir `.env` a Git (está en `.gitignore`).
- Usar Row Level Security (RLS) en Supabase en producción.

---

## 🗺️ Roadmap

- [ ] Notificaciones proactivas (alertas programadas)
- [ ] Metas de ahorro
- [ ] Múltiples monedas
- [ ] Exportar a Excel
- [ ] Dashboard web (opcional)
