import os
import io

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

from service.gost_parser import (
    REGION_DESIGNATION, REGION_NAME, REGION_FORMAT, REGION_PRIMARY_PARENT,
)

# Настройка пути tesseract для Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Порог: если в области меньше этого числа «значимых» символов электронного
# текста — считаем графу отсканированной и запускаем OCR только по ней.
_MIN_ELECTRONIC_CHARS = 3


class OCRService:
    def __init__(self, tesseract_cmd: str = None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # ------------------------------------------------------------------
    # Полный текст (запасной режим / отладка)
    # ------------------------------------------------------------------
    def extract_text_from_pdf(self, pdf_path: str, lang: str = "rus+eng") -> str:
        absolute_path = os.path.abspath(pdf_path)
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"Файл не найден по пути: '{absolute_path}'")
        doc = fitz.open(absolute_path)
        return self._extract_text_from_doc(doc, lang)

    def extract_text_from_bytes(self, pdf_bytes: bytes, lang: str = "rus+eng") -> str:
        """Извлекает весь текст из PDF, переданного как байты (BYTEA из БД)."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return self._extract_text_from_doc(doc, lang)

    def _extract_text_from_doc(self, doc, lang: str) -> str:
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if len(text.strip()) > 50:
                full_text.append(text)
            else:
                full_text.append(self._ocr_region(page, page.rect, lang, rotate=0))
        doc.close()
        return "\n\n--- Page Break ---\n\n".join(full_text)

    # ------------------------------------------------------------------
    # Основной режим: чтение фиксированных граф ГОСТ-листа
    # ------------------------------------------------------------------
    def extract_gost_regions_from_bytes(
        self, pdf_bytes: bytes, lang: str = "rus+eng"
    ) -> dict[str, str]:
        """Извлекает текст граф основной надписи с первого листа чертежа.

        ГОСТ задаёт фиксированные пропорции, поэтому каждая графа берётся из
        своей области листа. Для каждой графы сначала пробуем электронный текст,
        а если его нет — распознаём OCR только эту область (быстрее и точнее).
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc[0]
            return {
                "designation": self._region_text(page, REGION_DESIGNATION, lang),
                "name": self._region_text(page, REGION_NAME, lang),
                "format": self._region_text(page, REGION_FORMAT, lang),
                "primary_parent": self._region_text(
                    page, REGION_PRIMARY_PARENT, lang, rotate=90
                ),
            }
        finally:
            doc.close()

    def _region_text(self, page, frac_rect, lang: str, rotate: int = 0) -> str:
        """Возвращает текст области, заданной долями (x0,y0,x1,y1)."""
        w, h = page.rect.width, page.rect.height
        fx0, fy0, fx1, fy1 = frac_rect
        rect = fitz.Rect(fx0 * w, fy0 * h, fx1 * w, fy1 * h)

        text = page.get_text("text", clip=rect).strip()
        significant = sum(c.isalnum() for c in text)
        if significant >= _MIN_ELECTRONIC_CHARS:
            return text
        # Электронного текста в графе нет — распознаём только её
        return self._ocr_region(page, rect, lang, rotate=rotate)

    def _ocr_region(self, page, rect, lang: str, rotate: int = 0) -> str:
        """OCR одной области листа с увеличением для точности распознавания."""
        zoom = 4.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        if rotate:
            # Графа «Перв. примен.» повёрнута: текст читается снизу вверх
            img = img.rotate(-rotate, expand=True)
        return pytesseract.image_to_string(img, lang=lang).strip()
