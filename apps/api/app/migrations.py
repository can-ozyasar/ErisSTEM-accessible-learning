"""PostgreSQL migration dosyalarını sürüm kaydıyla uygular."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


def apply_postgres_migrations(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    directory = Path(__file__).parent.parent / "migrations"
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(255) PRIMARY KEY)")
        )
        applied = {
            row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))
        }
        for migration in sorted(directory.glob("*.sql")):
            if migration.name in applied:
                continue
            connection.exec_driver_sql(migration.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": migration.name},
            )
