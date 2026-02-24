"""Supabase client service."""
from supabase import create_client, Client
from flask import current_app


class SupabaseService:
    """Supabase client wrapper."""

    _client: Client = None

    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance."""
        if cls._client is None:
            url = current_app.config['SUPABASE_URL']
            key = current_app.config['SUPABASE_KEY']

            if not url or not key:
                raise ValueError("Supabase URL and KEY must be configured")

            cls._client = create_client(url, key)

        return cls._client

    @classmethod
    def reset_client(cls):
        """Reset client instance (useful for testing)."""
        cls._client = None
