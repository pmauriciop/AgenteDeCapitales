-- ─────────────────────────────────────────────────────────────────
-- supabase/migrations/001_initial_schema.sql
-- Esquema inicial del Agente de Capitales.
-- Ejecutar en el SQL Editor de Supabase (una sola vez).
-- ─────────────────────────────────────────────────────────────────

-- Habilitar extensión UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ─────────────────────────────────────────────
--  USERS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT  UNIQUE NOT NULL,
    name        TEXT    NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE  users IS 'Usuarios registrados vía Telegram.';
COMMENT ON COLUMN users.telegram_id IS 'ID numérico del usuario en Telegram.';


-- ─────────────────────────────────────────────
--  TRANSACTIONS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',  -- encriptado con Fernet
    type        TEXT    NOT NULL CHECK (type IN ('income', 'expense')),
    date        DATE    NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON transactions(user_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_user_category
    ON transactions(user_id, category);

COMMENT ON TABLE  transactions IS 'Registro de ingresos y gastos del usuario.';
COMMENT ON COLUMN transactions.description IS 'Descripción encriptada con Fernet AES-128.';


-- ─────────────────────────────────────────────
--  BUDGETS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budgets (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category     TEXT    NOT NULL,
    limit_amount NUMERIC(12, 2) NOT NULL CHECK (limit_amount > 0),
    month        CHAR(7) NOT NULL,  -- formato YYYY-MM
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, category, month)
);

CREATE INDEX IF NOT EXISTS idx_budgets_user_month
    ON budgets(user_id, month);

COMMENT ON TABLE  budgets IS 'Presupuestos mensuales por categoría.';
COMMENT ON COLUMN budgets.month IS 'Mes en formato YYYY-MM (ej: 2026-02).';


-- ─────────────────────────────────────────────
--  RECURRING TRANSACTIONS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recurring (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',  -- encriptado con Fernet
    frequency   TEXT    NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
    next_date   DATE    NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recurring_user_active
    ON recurring(user_id, active, next_date);

COMMENT ON TABLE  recurring IS 'Transacciones periódicas (Netflix, alquiler, sueldo, etc.).';


-- ─────────────────────────────────────────────
--  ROW LEVEL SECURITY (RLS)
--  Cada usuario solo puede ver sus propios datos.
--  Requiere autenticación Supabase activada.
-- ─────────────────────────────────────────────

-- Habilitar RLS en todas las tablas
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE recurring    ENABLE ROW LEVEL SECURITY;

-- Nota: El bot usa la service_key (bypassa RLS).
-- Si en el futuro se agrega un frontend web, definir políticas por auth.uid().
