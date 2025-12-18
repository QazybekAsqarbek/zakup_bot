from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from src.config import DB_PATH

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False) # Telegram User ID
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    quotes = relationship("Quote", back_populates="project")

class Quote(Base):
    __tablename__ = 'quotes'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    supplier_name = Column(String)
    raw_text_source = Column(String) # Имя файла или "text message"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    items = relationship("QuoteItem", back_populates="quote")
    project = relationship("Project", back_populates="quotes")

class QuoteItem(Base):
    __tablename__ = 'quote_items'
    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey('quotes.id'))
    name = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    price_per_unit = Column(Float)
    currency = Column(String)
    total_price = Column(Float)
    
    quote = relationship("Quote", back_populates="items")

# Инициализация БД
engine = create_engine(DB_PATH, echo=False)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
