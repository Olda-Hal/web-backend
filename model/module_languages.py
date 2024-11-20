from sqlalchemy import Column, Integer, ForeignKey
from . import Base


class ModuleLanguages(Base):
    __tablename__ = 'module_languages'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4'
    }
    id = Column(
        Integer, 
        primary_key=True, 
        nullable=False)
    module_id = Column(
        Integer, 
        ForeignKey('modules.id'), 
        nullable=False)
    language_id = Column(
        Integer,
        ForeignKey('languages.id'),
        nullable=False)