from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QMessageBox, QFileDialog,
    QTableWidgetItem, QWidget, QPushButton, QTableWidget, QLabel, QHBoxLayout,
    QMenuBar, QMenu, QStatusBar, QHeaderView, QAbstractItemView,
    QTabWidget, QLineEdit, QStyle,
)

from ui.item_form_dialog import ItemFormDialog
from ui.parent_child_dialog import ParentChildDialog
from ui.product_tree_widget import ProductTreeWidget
from ui.product_graph_widget import ProductGraphWidget
from database import get_db
from sqlalchemy.exc import IntegrityError
from repository.item_repository import ItemRepository
from repository.parent_child_repository import (
    ParentChildRepository, CycleDetectedError, MultiplePrimaryParentsError,
)
from models.item import Item


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ТехАрхив - Электронный архив технической документации")
        self.resize(1000, 640)
        self._apply_window_icon()

        # Коннект к репозиториям
        self.db = get_db()
        self.repo = ItemRepository(self.db)
        self.pc_repo = ParentChildRepository(self.db)

        # Инициализация интерфейса
        self.init_ui()
        self.load_data_to_table()

    def _apply_window_icon(self):
        import os
        from PyQt6.QtGui import QIcon
        from resources import app_icon_path
        path = app_icon_path()
        if os.path.exists(path):
            self.setWindowIcon(QIcon(path))

    def init_ui(self):
        self.create_menu_bar()
        self.create_status_bar()

        # Основной layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Заголовок + поиск
        header_layout = QHBoxLayout()
        header = QLabel("Журнал документов")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E293B; margin-bottom: 4px;")
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Поиск по ID, обозначению или наименованию...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.setMaximumWidth(280)
        self.edit_search.setStyleSheet(
            "QLineEdit { padding: 6px 10px; border: 1px solid #CBD5E1; "
            "border-radius: 4px; background-color: white; }"
            "QLineEdit:focus { border-color: #3B82F6; }"
        )
        self.edit_search.textChanged.connect(self._apply_search_filter)
        header_layout.addWidget(self.edit_search)

        main_layout.addLayout(header_layout)

        # Таблица — показывает все версии всех элементов
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Обозначение", "Наименование", "№ изменения", "Инв.№", "Файл"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(4, 110)
        self.table.doubleClicked.connect(self.on_table_double_click)
        self.table.cellClicked.connect(self._on_cell_clicked)

        # Контекстное меню (правый клик)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Страница «Журнал» (таблица + № изменения + кнопки) внутри вкладки
        table_page_layout = QVBoxLayout()
        table_page_layout.setContentsMargins(8, 8, 8, 8)
        table_page_layout.setSpacing(8)
        table_page_layout.addWidget(self.table)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_export = QPushButton("Сохранить файл")
        self.btn_export.clicked.connect(self.on_export_file)
        self.btn_export.setEnabled(False)
        self.btn_export.setStyleSheet(
            "QPushButton { background-color: #8B5CF6; color: white; padding: 7px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #7C3AED; }"
            "QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }"
        )
        btn_layout.addWidget(self.btn_export)

        self.btn_edit = QPushButton("Редактировать")
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        self.btn_edit.setStyleSheet(
            "QPushButton { background-color: #3B82F6; color: white; padding: 7px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #2563EB; }"
            "QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }"
        )
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        self.btn_delete.setStyleSheet(
            "QPushButton { background-color: #EF4444; color: white; padding: 7px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #DC2626; }"
            "QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }"
        )
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addStretch()

        self.btn_add = QPushButton("Добавить")
        self.btn_add.clicked.connect(self.on_new_item)
        self.btn_add.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; padding: 7px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        btn_layout.addWidget(self.btn_add)

        table_page_layout.addLayout(btn_layout)

        table_page = QWidget()
        table_page.setLayout(table_page_layout)

        # Вкладка «Дерево изделия» — интерактивная структура применяемости
        self.tree_widget = ProductTreeWidget(self.db)
        self.tree_widget.edit_requested.connect(self._edit_item_by_id)
        self.tree_widget.view_file_requested.connect(self._view_file_by_id)
        self.tree_widget.add_child_requested.connect(self._add_child_for_id)
        self.tree_widget.structure_changed.connect(self.load_data_to_table)

        tree_page = QWidget()
        tree_page_layout = QVBoxLayout()
        tree_page_layout.setContentsMargins(8, 8, 8, 8)
        tree_page_layout.addWidget(self.tree_widget)
        tree_page.setLayout(tree_page_layout)

        # Вкладка «Граф изделия» — структура без дублирования узлов
        self.graph_widget = ProductGraphWidget(self.db)
        self.graph_widget.edit_requested.connect(self._edit_item_by_id)
        self.graph_widget.view_file_requested.connect(self._view_file_by_id)
        self.graph_widget.add_child_requested.connect(self._add_child_for_id)

        graph_page = QWidget()
        graph_page_layout = QVBoxLayout()
        graph_page_layout.setContentsMargins(8, 8, 8, 8)
        graph_page_layout.addWidget(self.graph_widget)
        graph_page.setLayout(graph_page_layout)

        # Вкладки: Журнал / Дерево изделия / Граф
        self.tabs = QTabWidget()
        self.tabs.addTab(table_page, "📋 Журнал")
        self.tabs.addTab(tree_page, "🌳 Дерево изделия")
        self.tabs.addTab(graph_page, "🔗 Граф")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #CBD5E1; border-radius: 4px; "
            "background-color: white; }"
            "QTabBar::tab { padding: 8px 20px; background-color: #F1F5F9; "
            "color: #475569; border-top-left-radius: 4px; border-top-right-radius: 4px; "
            "margin-right: 2px; font-weight: bold; }"
            "QTabBar::tab:selected { background-color: white; color: #1E293B; "
            "border-bottom: 2px solid #3B82F6; }"
            "QTabBar::tab:hover:!selected { background-color: #E2E8F0; }"
        )
        main_layout.addWidget(self.tabs)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Стиль фона
        self.setStyleSheet(
            "QMainWindow { background-color: #F8FAFC; }"
            "QTableWidget { background-color: white; gridline-color: #E2E8F0; "
            "border: 1px solid #CBD5E1; border-radius: 4px; font-size: 13px; }"
            "QTableWidget::item { padding: 6px 8px; }"
            "QTableWidget::item:selected { background-color: #DBEAFE; color: #1E293B; }"
            "QTableWidget::item:hover { background-color: #F1F5F9; }"
            "QHeaderView::section { background-color: #F1F5F9; color: #475569; "
            "font-weight: bold; padding: 8px; border: none; "
            "border-bottom: 2px solid #3B82F6; }"
            "QStatusBar { background-color: #F1F5F9; color: #64748B; font-size: 12px; }"
            "QMenuBar { background-color: #F1F5F9; }"
            "QMenuBar::item:selected { background-color: #DBEAFE; }"
            "QMenu { background-color: white; border: 1px solid #E2E8F0; }"
            "QMenu::item { padding: 6px 24px; }"
            "QMenu::item:selected { background-color: #DBEAFE; }"
        )

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        # --- Файл ---
        file_menu = menu_bar.addMenu("Файл")

        action_new = file_menu.addAction("Новый элемент")
        action_new.setShortcut("Ctrl+N")
        action_new.triggered.connect(self.on_new_item)

        action_import = file_menu.addAction("Импорт PDF")
        action_import.setShortcut("Ctrl+O")
        action_import.triggered.connect(self.on_import_pdf)

        file_menu.addSeparator()

        action_export = file_menu.addAction("Сохранить файл как...")
        action_export.setShortcut("Ctrl+Shift+S")
        action_export.triggered.connect(self.on_export_file)

        file_menu.addSeparator()

        action_exit = file_menu.addAction("Выход")
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)

        # --- Справка ---
        help_menu = menu_bar.addMenu("Справка")

        action_about = help_menu.addAction("О программе")
        action_about.triggered.connect(self.on_about)

    def create_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Готов к работе")
        self.setStatusBar(self.status_bar)

    # ------------------------------------------------------------------
    # Контекстное меню (правый клик по таблице)
    # ------------------------------------------------------------------
    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { padding: 4px; }"
            "QMenu::item { padding: 6px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background-color: #DBEAFE; }"
        )

        has_selection = self.table.currentRow() >= 0

        action_add = menu.addAction("Добавить элемент")
        action_add.triggered.connect(self.on_new_item)

        if has_selection:
            action_add_child = menu.addAction("Добавить связь")
            action_add_child.triggered.connect(self.on_add_child)

            menu.addSeparator()

            # Действия для файлов (только если у элемента есть file_data)
            selected_item = self._get_selected_item()
            has_file = selected_item is not None and selected_item.file_data is not None

            if has_file:
                action_view = menu.addAction("Просмотреть файл")
                action_view.triggered.connect(self.on_view_file)

                action_export = menu.addAction("Сохранить файл как...")
                action_export.triggered.connect(self.on_export_file)

                menu.addSeparator()

            action_edit = menu.addAction("Редактировать")
            action_edit.triggered.connect(self.on_edit_clicked)

            menu.addSeparator()

            action_delete = menu.addAction("Удалить")
            action_delete.triggered.connect(self.on_delete_clicked)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    # Роль данных для хранения item_id в ячейке таблицы
    ROLE_ITEM_ID = Qt.ItemDataRole.UserRole

    def _get_selected_item(self):
        """Возвращает объект Item по выделенной строке (id из UserRole, version из col 2)."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        first_cell = self.table.item(current_row, 0)
        ver_item = self.table.item(current_row, 2)
        if not first_cell or not ver_item:
            return None
        item_id = first_cell.data(self.ROLE_ITEM_ID)
        version = int(ver_item.text())
        return self.repo.get_by_id_and_version(item_id, version)

    def _create_item_from_data(self, data, auto_id=True):
        """Создаёт Item из данных диалога."""
        item_id = data["id"]
        if auto_id and item_id is None:
            item_id = self._get_latest_item_id_for_new()

        return Item(
            id=item_id,
            designation=data.get("designation"),
            name=data["name"],
            inventory_id=data.get("inventory_id"),
            version=data["version"],
            file_data=data.get("file_data"),
        )

    # ------------------------------------------------------------------
    # Вкладки и поиск
    # ------------------------------------------------------------------
    def _on_tab_changed(self, index: int):
        """При переходе на вкладку дерева/графа — обновляем их из БД."""
        if index == 1:
            self.tree_widget.refresh()
        elif index == 2:
            self.graph_widget.refresh()

    def _apply_search_filter(self, text: str = None):
        """Фильтрует строки таблицы по ID (скрытому), обозначению, наименованию или инв.№."""
        if text is None:
            text = self.edit_search.text()
        query = text.strip().lower()
        for row in range(self.table.rowCount()):
            parts = []
            # Скрытый ID из UserRole
            first_cell = self.table.item(row, 0)
            if first_cell:
                item_id = first_cell.data(self.ROLE_ITEM_ID)
                if item_id is not None:
                    parts.append(str(item_id))
            # col 0: Обозначение, col 1: Наименование, col 3: Инв.№
            for col in (0, 1, 3):
                cell = self.table.item(row, col)
                if cell:
                    parts.append(cell.text())
            row_text = " ".join(parts).lower()
            self.table.setRowHidden(row, bool(query) and query not in row_text)

    # ------------------------------------------------------------------
    # Обработчики сигналов дерева изделия
    # ------------------------------------------------------------------
    def _get_latest_item(self, item_id: int):
        version = self.repo.get_max_version(item_id)
        return self.repo.get_by_id_and_version(item_id, version)

    def _edit_item_by_id(self, item_id: int):
        item = self._get_latest_item(item_id)
        if item is None:
            QMessageBox.warning(self, "Предупреждение", f"Элемент {item_id} не найден")
            return

        dialog = ItemFormDialog(parent=self, mode="edit", item=item)
        if not dialog.exec():
            return

        data = dialog.get_data()
        try:
            name_changed = data["name"] != item.name
            desig_changed = data.get("designation") != (item.designation or "")
            inv_changed = data.get("inventory_id") != item.inventory_id
            file_changed = data["file_data"] is not None

            if not (name_changed or desig_changed or inv_changed or file_changed):
                self.load_data_to_table()
                return

            if name_changed or desig_changed:
                # Изменены ключевые поля — создаём новую № изменения
                new_version = self.repo.get_max_version(item.id) + 1
                new_item = Item(
                    id=item.id,
                    version=new_version,
                    designation=data.get("designation") or item.designation,
                    name=data["name"],
                    inventory_id=data.get("inventory_id"),
                    file_data=data["file_data"] if data["file_data"] is not None else item.file_data,
                )
                self.repo.save(new_item)
                self._auto_link_primary_parent(new_item, data)
                self.status_bar.showMessage(f"Элемент ID {item.id} обновлён (v{new_version})")
            else:
                # Изменены вторичные поля (инв.№, файл) — обновляем текущую № изменения
                item.inventory_id = data.get("inventory_id")
                if data["file_data"] is not None:
                    item.file_data = data["file_data"]
                self.repo.save(item)
                self.status_bar.showMessage(f"Элемент ID {item.id} v{item.version} обновлён")
            self.load_data_to_table()
        except IntegrityError as e:
            self.db.rollback()
            if getattr(e.orig, 'pgcode', None) == '23505':
                QMessageBox.warning(
                    self, "Конфликт данных",
                    "Инвентарный номер уже используется другим элементом.\n"
                    "Введите другой инвентарный номер."
                )
            else:
                QMessageBox.critical(self, "Ошибка базы данных", str(e))
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Ошибка базы данных", str(e))

    def _view_file_by_id(self, item_id: int):
        item = self._get_latest_item(item_id)
        if item is None or item.file_data is None:
            QMessageBox.warning(self, "Предупреждение", "У элемента нет прикреплённого файла")
            return
        self._open_pdf_viewer(item)

    def _add_child_for_id(self, parent_item_id: int):
        items = self.repo.get_latest_versions()
        if not items:
            QMessageBox.warning(self, "Предупреждение", "В базе нет элементов")
            return

        dialog = ParentChildDialog(
            parent=self, items=items, preselect_parent_id=parent_item_id,
        )
        if not dialog.exec():
            return

        data = dialog.get_data()
        try:
            self.pc_repo.save(data["parent_id"], data["child_id"], data["is_primary"])
            rel_type = "Первичная" if data["is_primary"] else "Заимствование"
            self.status_bar.showMessage(
                f"Связь: {data['parent_id']} → {data['child_id']} ({rel_type})"
            )
            self.tree_widget.refresh()
        except CycleDetectedError as e:
            QMessageBox.warning(self, "Цикл обнаружен", str(e))
        except MultiplePrimaryParentsError as e:
            QMessageBox.warning(self, "Конфликт применяемости", str(e))
        except ValueError as e:
            QMessageBox.warning(self, "Предупреждение", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка базы данных", str(e))

    # ------------------------------------------------------------------
    # Файл -> Новый / Контекстное меню -> Добавить элемент
    # ------------------------------------------------------------------
    def on_new_item(self):
        dialog = ItemFormDialog(parent=self, mode="new")
        if not dialog.exec():
            return

        data = dialog.get_data()
        try:
            new_item = self._create_item_from_data(data)
            self.repo.save(new_item)
            self._auto_link_primary_parent(new_item, data)
            self.load_data_to_table()
            self.status_bar.showMessage(f"Добавлен элемент: ID {new_item.id}")
        except IntegrityError as e:
            self.db.rollback()
            if getattr(e.orig, 'pgcode', None) == '23505':
                QMessageBox.warning(
                    self, "Конфликт данных",
                    "Инвентарный номер уже используется другим элементом.\n"
                    "Введите другой инвентарный номер."
                )
            else:
                QMessageBox.critical(self, "Ошибка базы данных", str(e))
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Ошибка базы данных", str(e))

    def _auto_link_primary_parent(self, child_item, data: dict):
        """Если OCR распознал «Перв. примен.», создаёт связь с родителем.

        Сопоставляет обозначение первичного изделия (графа «Перв. примен.»)
        с обозначением уже существующего элемента (с запасным поиском по
        наименованию). При совпадении — автоматически создаёт первичную связь
        parent → child.
        """
        parent_designation = data.get("primary_parent")
        if not parent_designation:
            return

        key = parent_designation.replace(" ", "").lower()
        match = None
        for it in self.repo.get_latest_versions():
            if it.id == child_item.id:
                continue
            desig = (it.designation or "").replace(" ", "").lower()
            name = (it.name or "").replace(" ", "").lower()
            if (desig and key in desig) or key in name:
                match = it
                break

        if match is None:
            self.status_bar.showMessage(
                f"Перв. примен. «{parent_designation}» не найдено среди элементов — "
                f"связь не создана"
            )
            return

        try:
            self.pc_repo.save(match.id, child_item.id, is_primary=True)
            self.status_bar.showMessage(
                f"Авто-связь: {match.id} → {child_item.id} (первичная применяемость)"
            )
        except (CycleDetectedError, MultiplePrimaryParentsError, ValueError):
            # Конфликт применяемости/цикл — молча пропускаем (элемент уже сохранён)
            pass

    # ------------------------------------------------------------------
    # Контекстное меню -> Добавить дочерний элемент
    # ------------------------------------------------------------------
    def on_add_child(self):
        selected = self._get_selected_item()
        self._add_child_for_id(selected.id if selected else None)

    # ------------------------------------------------------------------
    # Файл -> Импорт PDF
    # ------------------------------------------------------------------
    def on_import_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите PDF-документ", "", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        dialog = ItemFormDialog(parent=self, mode="import", file_path=file_path)
        if not dialog.exec():
            return

        data = dialog.get_data()
        try:
            new_item = self._create_item_from_data(data)
            self.repo.save(new_item)
            self._auto_link_primary_parent(new_item, data)
            self.load_data_to_table()
            self.status_bar.showMessage(f"Импортирован элемент: ID {new_item.id}")
        except IntegrityError as e:
            self.db.rollback()
            if getattr(e.orig, 'pgcode', None) == '23505':
                QMessageBox.warning(
                    self, "Конфликт данных",
                    "Инвентарный номер уже используется другим элементом.\n"
                    "Введите другой инвентарный номер."
                )
            else:
                QMessageBox.critical(self, "Ошибка базы данных", str(e))
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Ошибка базы данных", str(e))

    # ------------------------------------------------------------------
    # Таблица: двойной клик / кнопка «Редактировать»
    # ------------------------------------------------------------------
    def on_table_double_click(self, index):
        self._open_edit_dialog()

    def on_edit_clicked(self):
        self._open_edit_dialog()

    def _open_edit_dialog(self):
        item = self._get_selected_item()
        if item is None:
            QMessageBox.warning(self, "Предупреждение", "Ни одна запись не выбрана")
            return

        dialog = ItemFormDialog(parent=self, mode="edit", item=item)
        if not dialog.exec():
            return

        data = dialog.get_data()
        try:
            name_changed = data["name"] != item.name
            desig_changed = data.get("designation") != (item.designation or "")
            inv_changed = data.get("inventory_id") != item.inventory_id
            file_changed = data["file_data"] is not None

            if not (name_changed or desig_changed or inv_changed or file_changed):
                self.load_data_to_table()
                return

            if name_changed or desig_changed:
                # Изменены ключевые поля — создаём новую № изменения
                new_version = self.repo.get_max_version(item.id) + 1
                new_item = Item(
                    id=item.id,
                    version=new_version,
                    designation=data.get("designation") or item.designation,
                    name=data["name"],
                    inventory_id=data.get("inventory_id"),
                    file_data=data["file_data"] if data["file_data"] is not None else item.file_data,
                )
                self.repo.save(new_item)
                self._auto_link_primary_parent(new_item, data)
                self.status_bar.showMessage(f"Элемент ID {item.id} обновлён (v{new_version})")
            else:
                # Изменены вторичные поля (инв.№, файл) — обновляем текущую № изменения
                item.inventory_id = data.get("inventory_id")
                if data["file_data"] is not None:
                    item.file_data = data["file_data"]
                self.repo.save(item)
                self.status_bar.showMessage(f"Элемент ID {item.id} v{item.version} обновлён")
            self.load_data_to_table()
        except IntegrityError as e:
            self.db.rollback()
            if getattr(e.orig, 'pgcode', None) == '23505':
                QMessageBox.warning(
                    self, "Конфликт данных",
                    "Инвентарный номер уже используется другим элементом.\n"
                    "Введите другой инвентарный номер."
                )
            else:
                QMessageBox.critical(self, "Ошибка базы данных", str(e))
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Ошибка базы данных", str(e))

    # ------------------------------------------------------------------
    # Просмотр и экспорт файлов
    # ------------------------------------------------------------------
    def _update_action_buttons(self):
        """Включает/выключает кнопки в зависимости от выделения и наличия файла."""
        item = self._get_selected_item()
        has_file = item is not None and item.file_data is not None
        self.btn_export.setEnabled(has_file)
        self.btn_edit.setEnabled(item is not None)
        self.btn_delete.setEnabled(item is not None)

    def on_view_file(self):
        """Открывает диалог просмотра PDF-файла (оставлен для совместимости)."""
        item = self._get_selected_item()
        if item is None or item.file_data is None:
            QMessageBox.warning(self, "Предупреждение", "У выбранного элемента нет прикреплённого файла")
            return
        self._open_pdf_viewer(item)

    def _open_pdf_viewer(self, item):
        """Открывает диалог просмотра PDF с обработкой ошибок."""
        try:
            from ui.pdf_viewer_dialog import PdfViewerDialog
            dialog = PdfViewerDialog(parent=self, pdf_bytes=item.file_data, item_name=item.name)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть PDF:\n{e}")

    def on_export_file(self):
        """Сохраняет PDF-файл на диск."""
        item = self._get_selected_item()
        if item is None or item.file_data is None:
            QMessageBox.warning(self, "Предупреждение", "У выбранного элемента нет прикреплённого файла")
            return

        default_name = f"{item.name}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PDF-файл", default_name, "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "wb") as f:
                f.write(item.file_data)
            self.status_bar.showMessage(f"Файл сохранён: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------
    def on_delete_clicked(self):
        item = self._get_selected_item()
        if item is None:
            QMessageBox.warning(self, "Предупреждение", "Ни одна запись не выбрана")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить элемент ID {item.id}, № изменения {item.version}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.repo.delete(item)
                self.load_data_to_table()
                self.status_bar.showMessage("Запись успешно удалена")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка базы данных", str(e))

    def _get_latest_item_id_for_new(self) -> int:
        """Возвращает следующий доступный ID для нового элемента."""
        all_items = self.repo.get_all()
        if not all_items:
            return 1
        return max(it.id for it in all_items) + 1

    # ------------------------------------------------------------------
    # Справка -> О программе
    # ------------------------------------------------------------------
    def on_about(self):
        QMessageBox.about(
            self,
            "О программе",
            "ТехАрхив — электронный архив технической документации\n\n"
            "Распознавание (OCR) основной надписи чертежей по ГОСТ 2.104,\n"
            "ведение структуры изделия (дерево/граф применяемости)\n"
            "и хранение PDF-документов в PostgreSQL.",
        )

    # ------------------------------------------------------------------
    # Таблица: загрузка данных
    # ------------------------------------------------------------------
    def load_data_to_table(self):
        """Загружает все версии всех элементов, отсортированные по id и версии."""
        self.table.setRowCount(0)

        items = sorted(self.repo.get_all(), key=lambda it: (it.id, it.version))
        for i, item in enumerate(items):
            self.table.insertRow(i)
            # col 0: Обозначение (+ item_id в UserRole)
            desig_item = QTableWidgetItem(item.designation or "—")
            desig_item.setData(self.ROLE_ITEM_ID, item.id)
            self.table.setItem(i, 0, desig_item)
            # col 1: Наименование
            self.table.setItem(i, 1, QTableWidgetItem(item.name))
            # col 2: № изменения
            self.table.setItem(i, 2, QTableWidgetItem(str(item.version)))
            # col 3: Инв.№
            inv_text = str(item.inventory_id) if item.inventory_id is not None else "—"
            self.table.setItem(i, 3, QTableWidgetItem(inv_text))
            # col 4: Файл
            self._set_file_cell(i, item)

        self._update_action_buttons()

        # Повторно применяем фильтр поиска и обновляем дерево
        if hasattr(self, "edit_search"):
            self._apply_search_filter()
        if hasattr(self, "tree_widget"):
            self.tree_widget.refresh()
        self.status_bar.showMessage(f"Записей в журнале: {len(items)}")

    FILE_COL = 4

    def _set_file_cell(self, row: int, item):
        """Устанавливает ячейку «Файл» — ссылка просмотра + кнопка скачивания."""
        # Всегда очищаем предыдущее содержимое ячейки
        self.table.setCellWidget(row, self.FILE_COL, None)
        self.table.setItem(row, self.FILE_COL, None)

        if item.file_data:
            container = QWidget()
            container_layout = QHBoxLayout()
            container_layout.setContentsMargins(4, 2, 4, 2)
            container_layout.setSpacing(6)

            # Открыть PDF — компактная кликабельная ссылка
            link_label = QLabel("Открыть")
            link_label.setStyleSheet(
                "color: #2563EB; text-decoration: underline; padding: 0; font-size: 12px;"
            )
            link_label.setCursor(Qt.CursorShape.PointingHandCursor)
            link_label.setToolTip("Просмотреть PDF во встроенном просмотрщике")
            link_label.mousePressEvent = lambda e, it=item: self._open_pdf_viewer(it)
            container_layout.addWidget(link_label)

            # Кнопка скачивания — пилюля с иконкой, подогнанная по высоте строки
            dl_btn = QPushButton()
            dl_btn.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogSaveButton
            ))
            dl_btn.setFixedSize(12, 12)
            dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dl_btn.setToolTip("Сохранить файл на диск")
            dl_btn.setStyleSheet(
                "QPushButton { background-color: #EEF2FF; color: #1D4ED8; "
                "border: 1px solid #C7D2FE; border-radius: 4px; padding: 2px; }"
                "QPushButton:hover { background-color: #1D4ED8; color: white; "
                "border-color: #1D4ED8; }"
                "QPushButton:pressed { background-color: #1E40AF; }"
            )
            dl_btn.clicked.connect(lambda checked, it=item: self._export_item_file(it))
            container_layout.addWidget(dl_btn)

            container.setLayout(container_layout)
            self.table.setCellWidget(row, self.FILE_COL, container)
        else:
            self.table.setItem(row, self.FILE_COL, QTableWidgetItem("—"))

    def _on_cell_clicked(self, row: int, column: int):
        """Обработка клика по ячейке (зарезервировано для будущих расширений)."""
        pass

    def _export_item_file(self, item):
        """Сохраняет PDF-файл на диск для указанного элемента."""
        if item is None or item.file_data is None:
            return
        default_name = f"{item.name}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PDF-файл", default_name, "PDF Files (*.pdf)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "wb") as f:
                f.write(item.file_data)
            self.status_bar.showMessage(f"Файл сохранён: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

    def closeEvent(self, event):
        self.db.close()
        event.accept()
