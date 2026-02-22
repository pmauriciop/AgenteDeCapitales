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

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_client() -> Client:
    """
    Retorna la instancia única del cliente Supabase (patrón singleton).
    Se inicializa la primera vez que se llama.
    """
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
