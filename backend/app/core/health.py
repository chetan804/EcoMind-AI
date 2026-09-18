import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine


logger = logging.getLogger("ecomind.health")


def database_is_available(engine: Engine) -> bool:
    """Return whether the database accepts a minimal, read-only probe."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        return False
    return True
