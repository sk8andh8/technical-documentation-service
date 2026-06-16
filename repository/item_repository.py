from sqlalchemy.orm import Session
from sqlalchemy import func
from models.item import Item
from typing import List, Optional


class ItemRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_by_id_and_version(self, id: int, version: int) -> type[Item] | None:
        return self.db.query(Item).filter(Item.id == id, Item.version == version).first()

    def get_all(self) -> list[type[Item]]:
        return self.db.query(Item).all()

    def get_latest_versions(self) -> list[Item]:
        """Возвращает только последнюю № изменения каждого элемента (по id)."""
        # Подзапрос: максимальная № изменения для каждого id
        subq = (
            self.db.query(
                Item.id,
                func.max(Item.version).label("max_version")
            )
            .group_by(Item.id)
            .subquery()
        )
        return (
            self.db.query(Item)
            .join(subq, (Item.id == subq.c.id) & (Item.version == subq.c.max_version))
            .order_by(Item.id)
            .all()
        )

    def get_versions_for_id(self, item_id: int) -> list[Item]:
        """Возвращает все версии элемента с данным id, отсортированные по версии."""
        return (
            self.db.query(Item)
            .filter(Item.id == item_id)
            .order_by(Item.version)
            .all()
        )

    def get_max_version(self, item_id: int) -> int:
        """Возвращает максимальную № изменения для данного id."""
        result = (
            self.db.query(func.max(Item.version))
            .filter(Item.id == item_id)
            .scalar()
        )
        return result if result is not None else 0

    def save(self, item: Item) -> Item:
        merged = self.db.merge(item)
        self.db.commit()
        self.db.refresh(merged)
        return merged

    def delete(self, item: Item) -> None:
        self.db.delete(item)
        self.db.commit()