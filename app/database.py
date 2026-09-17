import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_FILE = DATA_DIR / "raksha.db"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Allow database URL override via environment variables (e.g. for testing)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    db_path_env = os.getenv("RAKSHA_DB_PATH")
    if db_path_env:
        target_path = Path(db_path_env).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{target_path.as_posix()}"
    else:
        DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Enable foreign keys for SQLite connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_override=None):
    """Create all database tables and ensure Phase 3 schema migrations."""
    target_engine = engine_override or engine
    Base.metadata.create_all(bind=target_engine)

    # SQLite schema migration: verify and add risk_score column if missing
    try:
        with target_engine.connect() as conn:
            columns_info = conn.exec_driver_sql("PRAGMA table_info(maintenance_requests)").fetchall()
            col_names = [col[1] for col in columns_info]
            if col_names and "risk_score" not in col_names:
                conn.exec_driver_sql("ALTER TABLE maintenance_requests ADD COLUMN risk_score FLOAT DEFAULT 0.0")
                conn.commit()
    except Exception:
        pass


def reset_db(engine_override=None):
    """Drop and recreate all database tables."""
    target_engine = engine_override or engine
    Base.metadata.drop_all(bind=target_engine)
    Base.metadata.create_all(bind=target_engine)
