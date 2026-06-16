from sqlalchemy.orm import Session
from models.parent_child import ParentChild
from typing import List, Optional


class CycleDetectedError(Exception):
    """Вызывается при попытке создать связь, образующую цикл."""
    pass


class MultiplePrimaryParentsError(Exception):
    """Вызывается при попытке назначить ребёнку второго первичного родителя."""
    pass


class ParentChildRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_all(self) -> list[ParentChild]:
        return self.db.query(ParentChild).all()

    def get_children(self, parent_id: int) -> list[ParentChild]:
        return (
            self.db.query(ParentChild)
            .filter(ParentChild.parent_id == parent_id)
            .all()
        )

    def get_parents(self, child_id: int) -> list[ParentChild]:
        return (
            self.db.query(ParentChild)
            .filter(ParentChild.child_id == child_id)
            .all()
        )

    def get_one(self, parent_id: int, child_id: int) -> Optional[ParentChild]:
        return (
            self.db.query(ParentChild)
            .filter(
                ParentChild.parent_id == parent_id,
                ParentChild.child_id == child_id,
            )
            .first()
        )

    def get_latest_version_id_map(self) -> dict[int, int]:
        """Возвращает маппинг item_id → latest_version для всех изделий."""
        from sqlalchemy import func
        rows = (
            self.db.query(
                ParentChild.parent_id,
                func.max(ParentChild.child_id)
            )
            .group_by(ParentChild.parent_id)
            .all()
        )
        # Простой подход: собираем все уникальные id из обеих колонок
        all_ids = set()
        all_rels = self.db.query(ParentChild).all()
        for rel in all_rels:
            all_ids.add(rel.parent_id)
            all_ids.add(rel.child_id)
        return {item_id: True for item_id in all_ids}

    def _would_create_cycle(self, parent_id: int, child_id: int) -> bool:
        """Проверяет, создаст ли добавление связи parent→child цикл."""
        # BFS от child_id вверх по дереву (ищем parent_id среди предков)
        visited = set()
        queue = [parent_id]
        while queue:
            current = queue.pop(0)
            if current == child_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            # Нходим всех родителей текущего узла
            parents = (
                self.db.query(ParentChild.parent_id)
                .filter(ParentChild.child_id == current)
                .all()
            )
            for (pid,) in parents:
                if pid not in visited:
                    queue.append(pid)
        return False

    def _has_primary_parent(self, child_id: int, exclude_parent_id: int = None) -> bool:
        """Проверяет, есть ли у ребёнка уже первичный Перв. примен.."""
        query = self.db.query(ParentChild).filter(
            ParentChild.child_id == child_id,
            ParentChild.is_primary == True,
        )
        if exclude_parent_id is not None:
            query = query.filter(ParentChild.parent_id != exclude_parent_id)
        return query.first() is not None

    def save(self, parent_id: int, child_id: int, is_primary: bool = True) -> ParentChild:
        # Валидация: нельзя быть своим собственным родителем
        if parent_id == child_id:
            raise ValueError("Элемент не может быть родителем самого себя")

        existing = self.get_one(parent_id, child_id)

        # Проверка цика (только при создании новой связи)
        if existing is None and self._would_create_cycle(parent_id, child_id):
            raise CycleDetectedError(
                f"Связь {parent_id} → {child_id} создаст цикл в дереве"
            )

        # Проверка: у ребёнка может быть только один первичный Перв. примен.
        if is_primary and self._has_primary_parent(child_id, exclude_parent_id=parent_id):
            raise MultiplePrimaryParentsError(
                f"У элемента {child_id} уже есть первичный Перв. примен.. "
                f"Используйте «Заимствование» для дополнительных связей."
            )

        if existing:
            existing.is_primary = is_primary
            self.db.commit()
            self.db.refresh(existing)
            return existing

        rel = ParentChild(parent_id=parent_id, child_id=child_id, is_primary=is_primary)
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def delete(self, parent_id: int, child_id: int) -> None:
        rel = self.get_one(parent_id, child_id)
        if rel:
            self.db.delete(rel)
            self.db.commit()
