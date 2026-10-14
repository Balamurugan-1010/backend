import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(ROOT_ENV):
    load_dotenv(dotenv_path=ROOT_ENV, override=True)
else:
    load_dotenv()

logger = logging.getLogger("talentmatch.database")

# Database URL configuration
# Supports: Supabase PostgreSQL, local PostgreSQL, or SQLite fallback
is_vercel = bool(os.getenv("VERCEL"))
fallback_sqlite = "sqlite:////tmp/talentmatch.db" if is_vercel else "sqlite:///./talentmatch.db"

DATABASE_URL = os.getenv("DATABASE_URL", fallback_sqlite)

# Supabase/Vercel sometimes provides postgres:// but SQLAlchemy 2.0 requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# PostgreSQL pool settings tuned for serverless (short-lived connections)
pool_kwargs = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    pool_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 300,
    })

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        **pool_kwargs
    )
    # Test connection
    with engine.connect() as conn:
        logger.info(f"Connected to database successfully using: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
except Exception as e:
    logger.warning(f"Could not connect to configured DATABASE_URL ({e}). Falling back to SQLite.")
    DATABASE_URL = fallback_sqlite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
