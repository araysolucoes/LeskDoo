from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
class ManagedVM(Base):
    __tablename__ = 'managed_vms'
    uuid = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    username = Column(String(64), nullable=False)
    ssh_port = Column(Integer, nullable=True)
    stage = Column(String(40), nullable=False, default='registered')
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

def connect(url):
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
