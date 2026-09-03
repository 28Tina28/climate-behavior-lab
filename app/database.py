from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DATA_DIR = os.path.join(PROJECT_DIR, "data")
IS_VERCEL = os.environ.get("VERCEL") == "1"

# 优先使用云端 Postgres（Neon / Vercel Postgres），让网页上传的数据永久保存；
# 未配置 DATABASE_URL 时回退到本地 SQLite（/tmp 或项目 data/ 目录）。
PG_URL = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
          or os.environ.get("POSTGRES_URL_NON_POOLING") or "").strip()

if PG_URL:
    if PG_URL.startswith("postgres://"):
        PG_URL = "postgresql+psycopg2://" + PG_URL[len("postgres://"):]
    elif PG_URL.startswith("postgresql://"):
        PG_URL = "postgresql+psycopg2://" + PG_URL[len("postgresql://"):]
    # 无服务器环境不保留连接池，避免跨实例复用失效连接
    from sqlalchemy.pool import NullPool
    engine = create_engine(PG_URL, pool_pre_ping=True, poolclass=NullPool)
else:
    if IS_VERCEL:
        DATA_DIR = os.environ.get("DATA_DIR", "/tmp/data")
    else:
        DATA_DIR = os.environ.get("DATA_DIR", PROJECT_DATA_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)

    DB_PATH = os.path.join(DATA_DIR, "observations.db")
    if not os.path.exists(DB_PATH):
        seed_db = os.path.join(PROJECT_DATA_DIR, "observations.db")
        if os.path.exists(seed_db):
            os.makedirs(DATA_DIR, exist_ok=True)
            shutil.copy2(seed_db, DB_PATH)

    engine = create_engine("sqlite:///" + DB_PATH.replace(os.sep, "/"),
                           connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
