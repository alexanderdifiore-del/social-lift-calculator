"""SQLite persistence for Lollie."""

from lollie.db.connection import get_connection, get_db_path, init_database

__all__ = ["get_connection", "get_db_path", "init_database"]
