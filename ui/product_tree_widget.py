"""Интерактивное дерево изделия (применяемость, BOM).

Строит дерево из связей parent_child: корни — элементы без родителей,
дети раскрываются рекурсивно. Заимствованные связи (is_primary=FALSE)
помечаются отдельной иконкой/цветом. Один и тот же элемент может
встречаться в дереве несколько раз (первичная + заимствованные точки).
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QMessageBox,
)

from repository.item_repository import ItemRepository
from repository.parent_child_repository import ParentChildRepository

# Роли данных в элементах дерева
ROLE_ITEM_ID = Qt.ItemDataRole.UserRole
ROLE_PARENT_ID = Qt.ItemDataRole.UserRole + 1
ROLE_IS_PRIMARY = Qt.ItemDataRole.UserRole + 2


class ProductTreeWidget(QWidget):
    """Виджет вкладки «Дерево изделия»."""

    # Сигналы наружу (MainWindow подключает свои обработчики)
    edit_requested = pyqtSignal(int)          # item_id
    view_file_requested = pyqtSignal(int)     # item_id
    add_child_requested = pyqtSignal(int)     # parent_item_id
    structure_changed = pyqtSignal()          # после удаления связи

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.repo = ItemRepository(db_session)
        self.pc_repo = ParentChildRepository(db_session)

        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # --- Панель инструментов ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #3B82F6; color: white; padding: 6px 14px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #2563EB; }"
        )
        toolbar.addWidget(self.btn_refresh)

        self.btn_expand = QPushButton("Развернуть всё")
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_expand.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; "
            "background-color: #F1F5F9; color: #475569; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        toolbar.addWidget(self.btn_expand)

        self.btn_collapse = QPushButton("Свернуть всё")
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        self.btn_collapse.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; "
            "background-color: #F1F5F9; color: #475569; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        toolbar.addWidget(self.btn_collapse)

        toolbar.addStretch()

        # Легенда
        legend = QLabel(
            '<span style="color:#1E293B;">●</span> первичная применяемость&nbsp;&nbsp;'
            '<span style="color:#9333EA;">◌</span> заимствование'
        )
        legend.setStyleSheet("color: #64748B; font-size: 12px;")
        toolbar.addWidget(legend)

        layout.addLayout(toolbar)

        # --- Дерево ---
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(
            ["Элемент", "Наименование", "№ изменения", "Инв.№", "Применяемость"]
        )
        self.tree.setAlternatingRowColors(True)
        self.tree.header().resizeSection(0, 360)
        self.tree.header().resizeSection(1, 220)
        self.tree.header().resizeSection(3, 64)
        self.tree.setStyleSheet(
            "QTreeWidget { background-color: white; border: 1px solid #CBD5E1; "
            "border-radius: 4px; font-size: 13px; }"
            "QTreeWidget::item { padding: 4px; }"
            "QTreeWidget::item:selected { background-color: #DBEAFE; color: #1E293B; }"
            "QHeaderView::section { background-color: #F1F5F9; color: #475569; "
            "font-weight: bold; padding: 6px; border: none; "
            "border-bottom: 2px solid #3B82F6; }"
        )
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree, stretch=1)

        # --- Информация ---
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #64748B; font-style: italic;")
        layout.addWidget(self.lbl_info)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Построение дерева
    # ------------------------------------------------------------------
    def refresh(self):
        """Перестраивает дерево из БД."""
        self.tree.clear()

        items = {it.id: it for it in self.repo.get_latest_versions()}
        relations = self.pc_repo.get_all()

        children_map: dict[int, list] = {}
        has_parent: set[int] = set()
        has_children: set[int] = set()
        for rel in relations:
            children_map.setdefault(rel.parent_id, []).append(rel)
            has_parent.add(rel.child_id)
            has_children.add(rel.parent_id)

        # Глобальная роль элемента в структуре (не зависит от точки в дереве)
        self._roles = {
            item_id: self._classify(item_id, has_parent, has_children)
            for item_id in items
        }

        # Корни: элементы без родителей (включая изолированные)
        root_ids = [item_id for item_id in items if item_id not in has_parent]

        for root_id in sorted(root_ids):
            node = self._build_node(items, children_map, root_id,
                                    parent_id=None, is_primary=True, path=set())
            self.tree.addTopLevelItem(node)

        self.tree.expandAll()

        n_items = len(items)
        n_rels = len(relations)
        n_roots = len(root_ids)
        self.lbl_info.setText(
            f"Элементов: {n_items}  |  Связей: {n_rels}  |  Корневых узлов: {n_roots}"
        )

    @staticmethod
    def _classify(item_id: int, has_parent: set, has_children: set) -> str:
        """Глобальная роль элемента: Изделие (корень) / Сборка / Деталь (лист)."""
        is_root = item_id not in has_parent
        is_leaf = item_id not in has_children
        if is_root:
            return "Изделие"
        if is_leaf:
            return "Деталь"
        return "Сборка"

    def _build_node(self, items, children_map, item_id,
                    parent_id, is_primary, path: set) -> QTreeWidgetItem:
        item = items.get(item_id)
        name = item.name if item else f"<элемент {item_id} не найден>"
        designation = (item.designation or "") if item else ""
        version = f"{item.version}" if item else "—"
        inventory_id = str(item.inventory_id) if (item and item.inventory_id is not None) else "—"
        type_label = self._roles.get(item_id, "—")

        if parent_id is None:
            applicability = "изделие"
        elif is_primary:
            applicability = "первичная"
        else:
            applicability = "заимствование"

        # col0=Элемент, col1=Наименование, col2=№ изменения, col3=Инв.№, col4=Применяемость
        node = QTreeWidgetItem(
            [designation or name, name, version, inventory_id, applicability]
        )
        node.setData(0, ROLE_ITEM_ID, item_id)
        node.setData(0, ROLE_PARENT_ID, parent_id)
        node.setData(0, ROLE_IS_PRIMARY, is_primary)

        marker = "●" if (parent_id is None or is_primary) else "◌"
        prefix = {"Изделие": "🏭", "Сборка": "📦", "Деталь": "🔩"}.get(type_label, "🔩")
        tree_label = designation if designation else name
        node.setText(
            0, f"{prefix} {tree_label}  {marker if parent_id is not None else ''}".rstrip()
        )

        if not is_primary and parent_id is not None:
            # Заимствованная точка применения — фиолетовый курсив
            font = QFont()
            font.setItalic(True)
            for col in range(5):
                node.setFont(col, font)
                node.setForeground(col, QBrush(QColor("#9333EA")))
        elif parent_id is None:
            font = QFont()
            font.setBold(True)
            node.setFont(0, font)

        # Защита от циклов на уровне UI (БД их тоже не пускает)
        if item_id in path:
            warn = QTreeWidgetItem(["⚠ цикл — обход остановлен", "", "", "", ""])
            warn.setForeground(0, QBrush(QColor("#EF4444")))
            node.addChild(warn)
            return node

        for rel in sorted(children_map.get(item_id, []), key=lambda r: r.child_id):
            child = self._build_node(
                items, children_map, rel.child_id,
                parent_id=item_id, is_primary=rel.is_primary,
                path=path | {item_id},
            )
            node.addChild(child)

        return node

    # ------------------------------------------------------------------
    # Взаимодействие
    # ------------------------------------------------------------------
    def _selected_node(self) -> QTreeWidgetItem | None:
        nodes = self.tree.selectedItems()
        return nodes[0] if nodes else None

    def _on_double_click(self, node: QTreeWidgetItem, column: int):
        item_id = node.data(0, ROLE_ITEM_ID)
        if item_id is not None:
            self.edit_requested.emit(item_id)

    def _show_context_menu(self, pos):
        node = self.tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { padding: 4px; background-color: white; border: 1px solid #E2E8F0; }"
            "QMenu::item { padding: 6px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background-color: #DBEAFE; }"
        )

        if node is not None and node.data(0, ROLE_ITEM_ID) is not None:
            item_id = node.data(0, ROLE_ITEM_ID)
            parent_id = node.data(0, ROLE_PARENT_ID)

            action_add_child = menu.addAction("Добавить заим. примен.")
            action_add_child.triggered.connect(
                lambda: self.add_child_requested.emit(item_id)
            )

            menu.addSeparator()

            action_edit = menu.addAction("Редактировать элемент")
            action_edit.triggered.connect(
                lambda: self.edit_requested.emit(item_id)
            )

            item = self.repo.get_by_id_and_version(
                item_id, self.repo.get_max_version(item_id)
            )
            if item is not None and item.file_data is not None:
                action_view = menu.addAction("Просмотреть файл")
                action_view.triggered.connect(
                    lambda: self.view_file_requested.emit(item_id)
                )

            if parent_id is not None:
                menu.addSeparator()
                action_unlink = menu.addAction("Удалить перв. примен.")
                action_unlink.triggered.connect(
                    lambda: self._delete_relation(parent_id, item_id)
                )
        else:
            action_refresh = menu.addAction("Обновить")
            action_refresh.triggered.connect(self.refresh)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _delete_relation(self, parent_id: int, child_id: int):
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить связь {parent_id} → {child_id}?\n"
            f"Сами элементы останутся в базе.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.pc_repo.delete(parent_id, child_id)
            self.refresh()
            self.structure_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка базы данных", str(e))
