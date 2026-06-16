from sqlalchemy import Column, BigInteger, Boolean, PrimaryKeyConstraint
from database import Base


class ParentChild(Base):
    __tablename__ = 'parent_child'

    parent_id = Column(BigInteger, nullable=False)
    child_id = Column(BigInteger, nullable=False)
    is_primary = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        PrimaryKeyConstraint('parent_id', 'child_id'),
    )
