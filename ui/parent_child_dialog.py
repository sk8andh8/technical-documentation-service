from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QCheckBox, QPushButton, QLabel, QMessageBox, QGroupBox
)

from models.item import Item


class ParentChildDialog(QDialog):
    """Диалог создания связи Перв. примен. → Заим. примен. (применяемость).

    Связи привязаны к ID элемента, а не к версии.
    Все версии одного ID имеют одинаковые связи.
    В комбобоксах отображается только последняя № изменения каждого элемента.
    """

    def __init__(self, parent=None, items=None, preselect_parent_id=None):
        """
        Args:
            parent:             Перв. примен.ский виджет
            items:              список объектов Item (последние версии) для заполнения комбобоксов
            preselect_parent_id: ID родителя для предвыбора
        """
        super().__init__(parent)
        self.items = items or []
        self.setWindowTitle("Добавить связь применяемости")
        self.setMinimumWidth(420)
        self.setModal(True)

        self.init_ui(preselect_parent_id)

    def init_ui(self, preselect_parent_id=None):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # --- Связь ---
        rel_group = QGroupBox("Связь применяемости")
        rel_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #CBD5E1; "
            "border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
        )
        form = QFormLayout()
        form.setSpacing(8)

        # Перв. примен. — привязан к ID, не к версии
        self.combo_parent = QComboBox()
        self.combo_parent.setMinimumWidth(250)
        for item in self.items:
            self.combo_parent.addItem(f"{item.id} — {item.name}", item.id)
        if preselect_parent_id is not None:
            for i, item in enumerate(self.items):
                if item.id == preselect_parent_id:
                    self.combo_parent.setCurrentIndex(i)
                    break
        form.addRow("Перв. примен.:", self.combo_parent)

        # Заим. примен. — привязан к ID, не к версии
        self.combo_child = QComboBox()
        self.combo_child.setMinimumWidth(250)
        self._refresh_child_combo()
        self.combo_parent.currentIndexChanged.connect(self._refresh_child_combo)
        form.addRow("Заим. примен.:", self.combo_child)

        rel_group.setLayout(form)
        layout.addWidget(rel_group)

        # --- Тип применяемости ---
        type_group = QGroupBox("Тип применяемости")
        type_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #CBD5E1; "
            "border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
        )
        type_layout = QVBoxLayout()

        self.chk_primary = QCheckBox("Первичная")
        self.chk_primary.setChecked(True)
        self.chk_primary.setToolTip("Основная точка применения в структуре изделия")
        self.chk_primary.toggled.connect(self._on_primary_toggled)
        type_layout.addWidget(self.chk_primary)

        self.chk_borrowed = QCheckBox("Заимствование")
        self.chk_borrowed.setToolTip("Дополнительная / заимствованная точка применения")
        self.chk_borrowed.toggled.connect(self._on_type_toggled)
        type_layout.addWidget(self.chk_borrowed)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; padding: 6px 18px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet(
            "QPushButton { padding: 6px 18px; border-radius: 4px; }"
        )

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _refresh_child_combo(self):
        """Обновляет список доступных детей (исключая выбранного родителя).

        Связи привязаны к ID элемента — показываем только последнюю № изменения.
        """
        self.combo_child.clear()
        parent_id = self.combo_parent.currentData()
        for item in self.items:
            if item.id != parent_id:
                self.combo_child.addItem(f"{item.id} — {item.name}", item.id)

    def _on_type_toggled(self, checked):
        if checked:
            self.chk_primary.setChecked(False)

    def _on_primary_toggled(self, checked):
        if checked:
            self.chk_borrowed.setChecked(False)

    def on_save_clicked(self):
        if self.combo_child.currentData() is None:
            QMessageBox.warning(self, "Предупреждение", "Выберите ребёнка")
            return
        self.accept()

    def get_data(self):
        return {
            "parent_id": self.combo_parent.currentData(),
            "child_id": self.combo_child.currentData(),
            "is_primary": self.chk_primary.isChecked(),
        }
