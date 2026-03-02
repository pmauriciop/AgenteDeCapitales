"""
database/client.py
──────────────────
Singleton del cliente Supabase.
Todos los módulos del proyecto deben importar la DB desde aquí.

Uso:
    from database.client import get_client

    db = get_client()
    result = db.table("users").select("*").execute()
"""

from config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from supabase import Client, create_client

_client: Client | None = None


def get_client() -> Client:
    """
    Retorna la instancia única del cliente Supabase (patrón singleton).
    Usa la service_role key para bypassear RLS en operaciones del bot.
    """
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client
