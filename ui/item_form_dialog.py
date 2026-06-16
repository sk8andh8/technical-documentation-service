import os

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel, QFileDialog, QMessageBox,
    QGroupBox
)

from ui.workers import OCRWorker


class ItemFormDialog(QDialog):
    """Диалог создания / редактирования элемента (изделие/деталь/сборка).

    В режиме «new» поле ID скрыто (назначается автоматически).
    № изменения доступна для редактирования во всех режимах.
    Поле «Первичная применяемость» доступно для ручного ввода
    и заполняется автоматически при OCR.
    """

    def __init__(self, parent=None, mode="new", file_path=None, item=None):
        super().__init__(parent)
        self.mode = mode
        self.file_path = file_path
        self.file_bytes = None
        self.editing_item = item
        self._ocr_thread = None
        self._ocr_worker = None
        # Распознанные поля штампа (заполняются после OCR)
        self.detected_designation = None

        title = {
            "new": "Новый элемент",
            "import": "Импорт PDF",
            "edit": "Редактирование элемента",
        }.get(mode, "Элемент")
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)

        self.init_ui()

        if mode == "edit" and item:
            self.edit_id.setText(str(item.id))
            self.edit_designation.setText(item.designation or "")
            self.edit_name.setText(item.name)
            self.spin_version.setValue(item.version)
            if item.inventory_id is not None:
                self.edit_inventory_id.setText(str(item.inventory_id))
            # Показываем прикреплённый файл, если он есть
            if item.file_data:
                self.file_bytes = item.file_data
                self.lbl_filename.setText("Текущий файл (загружен из БД)")
                self.lbl_filename.setStyleSheet(
                    "color: #1E293B; padding: 4px; font-weight: bold;"
                )
                self.btn_ocr.setEnabled(True)
        elif mode in ("new", "import"):
            # ID назначается автоматически — скрываем
            self.lbl_id_row.setVisible(False)
            self.edit_id.setVisible(False)
            self.lbl_id_hint.setVisible(False)

        if file_path:
            self.load_file(file_path)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # --- Основная информация ---
        info_group = QGroupBox("Основная информация")
        info_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #CBD5E1; "
            "border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
        )
        form = QFormLayout()
        form.setSpacing(8)

        # Строка ID — видна в режиме edit как справочная (read-only), скрыта в new/import
        self.lbl_id_row = QLabel("")
        self.lbl_id_row.setStyleSheet("color: #64748B; font-style: italic;")
        self.edit_id = QLineEdit()
        self.edit_id.setReadOnly(True)
        self.edit_id.setMinimumWidth(200)
        self.edit_id.setStyleSheet(
            "QLineEdit { background-color: #F1F5F9; color: #64748B; }"
        )
        self.lbl_id_hint = QLabel("")
        self.lbl_id_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        form.addRow("", self.lbl_id_hint)

        # № изменения — доступна для редактирования во всех режимах
        self.spin_version = QSpinBox()
        self.spin_version.setRange(1, 9999)
        self.spin_version.setValue(1)
        self.spin_version.setToolTip("№ изменения элемента (назначается автоматически)")
        form.addRow("№ изменения:", self.spin_version)

        # Обозначение по ГОСТ 2.201 (децимальный номер) — отдельно от наименования
        self.edit_designation = QLineEdit()
        self.edit_designation.setPlaceholderText("напр. ЭМЦША.116.31100.000.00")
        self.edit_designation.setMinimumWidth(200)
        form.addRow("Обозначение:", self.edit_designation)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Введите наименование изделия/детали")
        self.edit_name.setMinimumWidth(200)
        form.addRow("Наименование:", self.edit_name)

        # Инвентарный номер — ручной ввод
        self.edit_inventory_id = QLineEdit()
        self.edit_inventory_id.setPlaceholderText("напр. 12345")
        self.edit_inventory_id.setMinimumWidth(200)
        self.edit_inventory_id.setToolTip("Инвентарный номер (Инв.№).\nЗаполняется вручную.")
        form.addRow("Инв.№:", self.edit_inventory_id)

        # Первичная применяемость —ручной ввод + автозаполнение по OCR
        self.edit_primary_parent = QLineEdit()
        self.edit_primary_parent.setPlaceholderText(
            "Обозначение изделия-родителя (напр. ЭМЦША.116.31100)"
        )
        self.edit_primary_parent.setMinimumWidth(200)
        self.edit_primary_parent.setToolTip(
            "Обозначение первичного изделия-применения (Перв. примен.).\n"
            "Заполняется автоматически при распознавании (OCR) или вручную.\n"
            "При сохранении создаётся связь Перв. примен.→Заим. примен., если Перв. примен. найден в архиве."
        )
        form.addRow("Перв. примен.:", self.edit_primary_parent)

        info_group.setLayout(form)
        layout.addWidget(info_group)

        # --- Файл ---
        file_group = QGroupBox("Файл (PDF)")
        file_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #CBD5E1; "
            "border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
        )
        file_vlayout = QVBoxLayout()
        file_layout = QHBoxLayout()

        self.lbl_filename = QLabel("Файл не выбран")
        self.lbl_filename.setStyleSheet("color: #94A3B8; padding: 4px;")
        self.lbl_filename.setWordWrap(True)

        self.btn_browse = QPushButton("Обзор...")
        self.btn_browse.clicked.connect(self.on_browse_clicked)
        self.btn_browse.setStyleSheet(
            "QPushButton { padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )

        file_layout.addWidget(self.lbl_filename, stretch=1)
        file_layout.addWidget(self.btn_browse)
        file_vlayout.addLayout(file_layout)

        # --- OCR: распознавание полей штампа по ГОСТ 2.104 ---
        ocr_layout = QHBoxLayout()

        self.btn_ocr = QPushButton("Распознать (OCR)")
        self.btn_ocr.setToolTip(
            "Распознать поля основной надписи чертежа (ГОСТ 2.104):\n"
            "обозначение изделия и первичную применяемость (Перв. примен.).\n"
            "Если Перв. примен. уже есть в архиве — связь создастся автоматически."
        )
        self.btn_ocr.clicked.connect(self.on_ocr_clicked)
        self.btn_ocr.setEnabled(False)
        self.btn_ocr.setStyleSheet(
            "QPushButton { background-color: #F59E0B; color: white; padding: 6px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #D97706; }"
            "QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }"
        )
        ocr_layout.addWidget(self.btn_ocr)

        self.lbl_ocr_status = QLabel("")
        self.lbl_ocr_status.setStyleSheet("color: #64748B; font-style: italic; padding: 4px;")
        self.lbl_ocr_status.setWordWrap(True)
        ocr_layout.addWidget(self.lbl_ocr_status, stretch=1)

        file_vlayout.addLayout(ocr_layout)

        # Результаты распознавания (заполняются после OCR)
        self.lbl_ocr_result = QLabel("")
        self.lbl_ocr_result.setStyleSheet(
            "color: #475569; font-size: 11px; padding: 4px; "
            "background-color: #F8FAFC; border-radius: 4px;"
        )
        self.lbl_ocr_result.setWordWrap(True)
        self.lbl_ocr_result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.lbl_ocr_result.setVisible(False)
        file_vlayout.addWidget(self.lbl_ocr_result)

        file_group.setLayout(file_vlayout)
        layout.addWidget(file_group)

        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; padding: 8px 24px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet(
            "QPushButton { padding: 8px 24px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_file(self, file_path):
        self.file_path = file_path
        filename = os.path.basename(file_path)
        self.lbl_filename.setText(filename)
        self.lbl_filename.setStyleSheet("color: #1E293B; padding: 4px; font-weight: bold;")

        try:
            with open(file_path, "rb") as f:
                self.file_bytes = f.read()
            self.btn_ocr.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")

    def on_browse_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите PDF-документ", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.load_file(file_path)

    # ------------------------------------------------------------------
    # OCR: распознавание полей штампа в фоновом потоке
    # ------------------------------------------------------------------
    def on_ocr_clicked(self):
        if not self.file_bytes:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите PDF-файл")
            return

        self.btn_ocr.setEnabled(False)
        self.lbl_ocr_status.setText("Распознавание...")
        self.lbl_ocr_result.setVisible(False)

        self._ocr_thread = QThread(self)
        self._ocr_worker = OCRWorker(pdf_bytes=self.file_bytes)
        self._ocr_worker.moveToThread(self._ocr_thread)

        self._ocr_thread.started.connect(self._ocr_worker.run)
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        # Завершение потока после получения результата или ошибки
        self._ocr_worker.finished.connect(self._ocr_thread.quit)
        self._ocr_worker.error.connect(self._ocr_thread.quit)
        self._ocr_thread.finished.connect(self._ocr_worker.deleteLater)
        self._ocr_thread.finished.connect(self._ocr_thread.deleteLater)

        self._ocr_thread.start()

    def _on_ocr_progress(self, message: str):
        self.lbl_ocr_status.setText(message)

    def _on_ocr_finished(self, fields):
        self.btn_ocr.setEnabled(True)

        if fields.is_empty():
            self.lbl_ocr_status.setText(
                "Поля штампа не распознаны — заполните вручную"
            )
            return

        self.lbl_ocr_status.setText("Распознавание завершено")

        # Запоминаем обозначение для автосвязи
        self.detected_designation = fields.designation

        # Автозаполнение полей (только если поле пустое — не затираем ручной ввод)
        if fields.designation and not self.edit_designation.text().strip():
            self.edit_designation.setText(fields.designation)
        if fields.name and not self.edit_name.text().strip():
            self.edit_name.setText(fields.name)
        if fields.primary_parent and not self.edit_primary_parent.text().strip():
            self.edit_primary_parent.setText(fields.primary_parent)

        # Показываем все распознанные поля
        rows = []
        if fields.designation:
            rows.append(f"Обозначение: {fields.designation}")
        if fields.primary_parent:
            rows.append(f"Перв. примен.: {fields.primary_parent}")
        if fields.name:
            rows.append(f"Наименование: {fields.name}")
        if fields.scale:
            rows.append(f"Масштаб: {fields.scale}")
        if fields.mass:
            rows.append(f"Масса: {fields.mass} кг")
        if fields.material:
            rows.append(f"Материал: {fields.material}")
        if fields.sheet_format:
            rows.append(f"Формат: {fields.sheet_format}")
        self.lbl_ocr_result.setText("\n".join(rows))
        self.lbl_ocr_result.setVisible(True)

    def _on_ocr_error(self, message: str):
        self.btn_ocr.setEnabled(True)
        self.lbl_ocr_status.setText("Ошибка распознавания")
        QMessageBox.warning(self, "Ошибка OCR", message)

    def on_save_clicked(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите наименование")
            return
        self.accept()

    def get_data(self):
        id_text = self.edit_id.text().strip()
        item_id = int(id_text) if id_text.isdigit() else None
        designation = self.edit_designation.text().strip() or None
        primary_parent = self.edit_primary_parent.text().strip() or None
        inv_text = self.edit_inventory_id.text().strip()
        inventory_id = int(inv_text) if inv_text.isdigit() else None
        return {
            "id": item_id,
            "name": self.edit_name.text().strip(),
            "designation": designation,
            "inventory_id": inventory_id,
            "version": self.spin_version.value(),
            "file_path": self.file_path,
            "file_data": self.file_bytes,
            "primary_parent": primary_parent,
        }
