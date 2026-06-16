from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from service.ocr_service import OCRService
from service.gost_parser import GostTitleBlockParser, GostFields


class OCRWorker(QObject):
    """Выполняет OCR и парсинг полей штампа по ГОСТ в фоновом потоке."""

    # Сигналы для общения с основным потоком GUI
    finished = pyqtSignal(object)  # отправляет GostFields обратно
    error = pyqtSignal(str)  # отправляет сообщение об ошибке
    progress = pyqtSignal(str)  # отправляет статус-сообщение

    def __init__(self, file_path: str = None, pdf_bytes: bytes = None):
        super().__init__()
        self.file_path = file_path
        self.pdf_bytes = pdf_bytes
        self.ocr_service = OCRService()
        self.parser = GostTitleBlockParser()

    @pyqtSlot()
    def run(self):
        try:
            self.progress.emit("Чтение граф основной надписи (ГОСТ 2.104)...")
            if self.pdf_bytes is not None:
                pdf_bytes = self.pdf_bytes
            elif self.file_path:
                with open(self.file_path, "rb") as f:
                    pdf_bytes = f.read()
            else:
                raise ValueError("Не указан источник PDF (файл или байты)")

            regions = self.ocr_service.extract_gost_regions_from_bytes(pdf_bytes)

            self.progress.emit("Разбор обозначения и первичной применяемости...")
            fields: GostFields = self.parser.parse_regions(regions)

            self.finished.emit(fields)
        except Exception as e:
            self.error.emit(str(e))
