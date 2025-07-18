import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "localhost"),
    "port": int(os.getenv("DATABASE_PORT", 5432)),
    "database": os.getenv("DATABASE_NAME", "chimera_db"),
    "user": os.getenv("DATABASE_USER", "postgres"),
    "password": os.getenv("DATABASE_PASSWORD"),
}

# Connection string для asyncpg
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@"
    f"{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
)

# Connection pool settings
POOL_MIN_SIZE = 10
POOL_MAX_SIZE = 20
POOL_MAX_INACTIVE_CONNECTION_LIFETIME = 300.0  # 5 минут

# Query timeouts
QUERY_TIMEOUT = 30  # секунд
STATEMENT_TIMEOUT = 60  # секунд