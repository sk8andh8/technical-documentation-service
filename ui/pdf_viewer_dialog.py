import os
import tempfile

from PyQt6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView, QPdfPageSelector
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QDoubleSpinBox, QGroupBox, QMessageBox,
)


class PdfViewerDialog(QDialog):
    """Диалог просмотра PDF-файла, сохранённого в базе данных."""

    def __init__(self, parent=None, pdf_bytes: bytes = None, item_name: str = ""):
        super().__init__(parent)
        self.pdf_bytes = pdf_bytes
        self.item_name = item_name
        # Предотвращаем сборку мусора
        self._byte_array = None
        self._buffer = None
        self._pdf_document = None

        self.setWindowTitle(f"Просмотр: {item_name}")
        self.resize(900, 700)
        self.setModal(True)

        self.init_ui()
        self._load_pdf()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Панель инструментов ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Выбор страницы
        self.page_selector = QPdfPageSelector(self)
        self.page_selector.setMinimumWidth(120)
        toolbar.addWidget(self.page_selector)

        toolbar.addStretch()

        # Режим масштабирования
        lbl_zoom = QLabel("Масштаб:")
        lbl_zoom.setStyleSheet("color: #475569; font-weight: bold;")
        toolbar.addWidget(lbl_zoom)

        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["По ширине", "Вписать в окно", "Произвольный"])
        self.combo_zoom.setCurrentIndex(0)
        self.combo_zoom.currentIndexChanged.connect(self._on_zoom_mode_changed)
        self.combo_zoom.setMinimumWidth(130)
        toolbar.addWidget(self.combo_zoom)

        # Коэффициент масштаба (виден только в режиме «Произвольный»)
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(0.1, 5.0)
        self.spin_zoom.setSingleStep(0.1)
        self.spin_zoom.setValue(1.0)
        self.spin_zoom.setSuffix("x")
        self.spin_zoom.valueChanged.connect(self._on_zoom_factor_changed)
        self.spin_zoom.setVisible(False)
        self.spin_zoom.setMinimumWidth(80)
        toolbar.addWidget(self.spin_zoom)

        toolbar.addStretch()

        # Кнопка «Открыть во внешней программе»
        self.btn_external = QPushButton("Открыть во внешней программе")
        self.btn_external.clicked.connect(self._open_externally)
        self.btn_external.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; "
            "background-color: #F1F5F9; color: #475569; font-weight: bold; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        toolbar.addWidget(self.btn_external)

        layout.addLayout(toolbar)

        # --- PDF viewer ---
        # QPdfView в PyQt6 требует явного аргумента parent (без него — TypeError)
        self.pdf_view = QPdfView(self)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self.pdf_view, stretch=1)

        # --- Информация ---
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #64748B; font-style: italic; padding: 2px;")
        layout.addWidget(self.lbl_info)

        # --- Кнопка «Закрыть» ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setDefault(True)
        self.btn_close.setStyleSheet(
            "QPushButton { padding: 8px 24px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _load_pdf(self):
        """Загружает PDF из байтов через QBuffer."""
        if not self.pdf_bytes:
            QMessageBox.warning(self, "Ошибка", "Нет данных файла для отображения")
            return

        try:
            self._byte_array = QByteArray(self.pdf_bytes)
            self._buffer = QBuffer(self._byte_array)
            self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            self._pdf_document = QPdfDocument(self)
            self._pdf_document.load(self._buffer)

            self.pdf_view.setDocument(self._pdf_document)
            self.page_selector.setDocument(self._pdf_document)

            # Информация о документе
            page_count = self._pdf_document.pageCount()
            self.lbl_info.setText(f"Страниц: {page_count}  |  Размер: {len(self.pdf_bytes) / 1024:.1f} КБ")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось открыть PDF:\n{e}")

    def _on_zoom_mode_changed(self, index):
        """Переключение режима масштабирования."""
        if index == 0:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.spin_zoom.setVisible(False)
        elif index == 1:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
            self.spin_zoom.setVisible(False)
        else:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.spin_zoom.setVisible(True)
            self.pdf_view.setZoomFactor(self.spin_zoom.value())

    def _on_zoom_factor_changed(self, value):
        """Изменение коэффициента масштаба."""
        if self.combo_zoom.currentIndex() == 2:
            self.pdf_view.setZoomFactor(value)

    def _open_externally(self):
        """Открывает PDF во внешней программе (просмотратель по умолчанию)."""
        if not self.pdf_bytes:
            return

        try:
            safe_name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in self.item_name)
            temp_path = os.path.join(tempfile.gettempdir(), f"{safe_name}.pdf")
            with open(temp_path, "wb") as f:
                f.write(self.pdf_bytes)
            QDesktopServices.openUrl(QUrl.fromLocalFile(temp_path))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{e}")
