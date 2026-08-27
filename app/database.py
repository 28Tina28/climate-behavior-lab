from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DATA_DIR = os.path.join(PROJECT_DIR, "data")
IS_VERCEL = os.environ.get("VERCEL") == "1"

# Vercel 的函数运行时文件系统是只读的，只有 /tmp 可写；
# 本地和 Railway 仍使用项目内的 data/ 目录。
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

DATABASE_URL = "sqlite:///" + DB_PATH.replace(os.sep, "/")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
