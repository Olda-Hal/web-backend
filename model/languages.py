from sqlalchemy import Column, Integer, Text

from . import Base


class Language(Base):
    __tablename__ = 'languages'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4'
    }
    id = Column(
        Integer, 
        primary_key=True, 
        nullable=False)
    name = Column(
        Text, 
        nullable=False)
    extension = Column(
        Text, 
        nullable=False)