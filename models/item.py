from sqlalchemy import Column, BigInteger, Integer, String, Boolean, LargeBinary, PrimaryKeyConstraint
from database import Base


class Item(Base):
    __tablename__ = 'item'

    id = Column(BigInteger, nullable=False)              # Порядковый номер (внутренний ID)
    version = Column(Integer, nullable=False, default=1)
    designation = Column(String, nullable=True)          # Обозначение по ГОСТ 2.201 (децимальный номер)
    name = Column(String, nullable=False)                # Наименование изделия/детали
    inventory_id = Column(Integer, nullable=True)        # Инвентарный номер (Инв.№)
    file_data = Column(LargeBinary, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'version'),
    )