from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func, DateTime


Base = declarative_base()


class BaseModel(Base):
    __abstract__ = True
    
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())