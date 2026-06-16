"""Парсер полей основной надписи (штампа) чертежа по ГОСТ 2.104 / ГОСТ 2.201.

ГОСТ задаёт фиксированные пропорции листа и расположение граф основной надписи,
поэтому ключевые поля извлекаются не из всего «сырого» текста, а из конкретных
областей листа (заданных в долях от ширины/высоты страницы). Это работает
одинаково и для электронного текста, и для отсканированного чертежа.

Извлекаются два главных поля (по ТЗ):
  - обозначение изделия (графа 2 основной надписи, правый нижний угол)
  - первичная применяемость (графа «Перв. примен.», повёрнутая на 90° слева)

Дополнительно (если удаётся) — наименование, масштаб, масса, материал, формат.
"""

import re
from dataclasses import dataclass, field


# Фиксированные области листа ГОСТ 2.104 (форма 1, А-форматы, портрет).
# Координаты — доли (x0, y0, x1, y1) от ширины/высоты страницы.
# rotate=90 означает, что текст в графе повёрнут (читается снизу вверх) —
# при OCR изображение области нужно повернуть перед распознаванием.
REGION_DESIGNATION = (0.45, 0.845, 0.97, 0.905)   # графа 2: обозначение
REGION_NAME = (0.40, 0.905, 0.78, 0.985)          # графа 1: наименование
REGION_FORMAT = (0.78, 0.98, 0.92, 1.0)           # графа «Формат» (ниже наименования, справа)
REGION_PRIMARY_PARENT = (0.0, 0.02, 0.14, 0.36)   # графа «Перв. примен.» (поворот 90°)


@dataclass
class GostFields:
    """Структурированные поля основной надписи чертежа."""
    designation: str | None = None      # Обозначение изделия (графа 2)
    primary_parent: str | None = None   # Перв. примен. — обозначение первичного изделия
    name: str | None = None             # Наименование изделия (графа 1)
    scale: str | None = None            # Масштаб (графа 6)
    mass: str | None = None             # Масса (графа 5)
    material: str | None = None         # Материал (графа 3)
    sheet_format: str | None = None     # Формат листа
    raw_text: str = field(default="", repr=False)

    def is_empty(self) -> bool:
        return not any(
            (self.designation, self.primary_parent, self.name,
             self.scale, self.mass, self.material)
        )


class GostTitleBlockParser:
    """Выделяет поля основной надписи из текста граф чертежа.

    Основной режим — `parse_regions`: получает словарь {имя_области: текст},
    извлечённый из фиксированных областей листа. Запасной режим — `parse`:
    ищет поля по всему тексту (для совместимости и нестандартных листов).
    """

    # Децимальное обозначение по ГОСТ 2.201, в т.ч. отраслевые варианты:
    #   ЭМЦША.116.31100.000.00, АБВГ.123456.789, МДУИ.466226.922-03.67
    # Код разработчика: 2–6 букв (кириллица/латиница), далее 3–5 числовых групп,
    # разделённых точкой; опционально код документа (СБ/ВО/ВП/ТУ/...).
    _RE_DESIGNATION = re.compile(
        r"([А-ЯЁA-Z][А-ЯЁA-Z0-9]{1,6})\s*[.,]\s*"
        r"(\d{1,6}(?:\s*[.,]\s*\d{1,6}){2,4})"
        r"(?:\s*(СБ|ВО|ВП|ТЧ|ГЧ|МЭ|МС|МЧ|ГБ|УЧ|ПМ|ТБ|РР|ПЗ|ТУ|Э\d?))?"
    )

    _RE_SCALE_LABELED = re.compile(
        r"Мас\s*шта\s*б\s*[:\-]?\s*(\d+(?:[.,]\d+)?\s*:\s*\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    )
    _RE_SCALE_TOKEN = re.compile(
        r"\b([125](?:[.,]5)?\s*:\s*(?:1|2|2[.,]5|4|5|10|15|20|25|40|50|75|100))\b"
    )
    _RE_MASS = re.compile(
        r"Мас\s*са\s*(?:,?\s*кг)?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    )
    _RE_MATERIAL = re.compile(
        r"((?:Сталь|Круг|Лист|Сплав|Бронза|Латунь|Чугун|Алюминий|Титан|"
        r"Полиамид|Капролон|Фторопласт|Резина|СЧ\s?\d+|Ст\s?\d+[а-я]*)"
        r"[^\n]{0,40}?ГОСТ\s*[\d.\-–]+)",
        re.IGNORECASE,
    )
    _RE_FORMAT = re.compile(r"(?:Формат\s*)?\b([АA][0-4]x?\d?)\b")
    _RE_FORMAT_LABELED = re.compile(
        r"Формат\s*[:\-]?\s*([АA][0-4]x?\d?)", re.IGNORECASE
    )

    # Служебные надписи штампа — не могут быть наименованием
    _STAMP_NOISE = {
        "изм", "лист", "листов", "№", "докум", "подп", "подпись", "дата",
        "разраб", "пров", "проверил", "т.контр", "н.контр", "утв", "утвердил",
        "масштаб", "масса", "литера", "лит", "формат", "копировал", "справ",
        "перв. примен", "перв", "примен", "гост", "ескд", "обозначение",
        "наименование", "разработал", "зона", "поз", "кол", "примечание",
        "инв", "взам", "дубл", "подл",
    }

    # ------------------------------------------------------------------
    # Основной режим: разбор по областям листа
    # ------------------------------------------------------------------
    def parse_regions(self, regions: dict[str, str]) -> GostFields:
        """Разбирает поля из текста фиксированных областей ГОСТ-листа.

        Args:
            regions: {"designation": текст_графы_2,
                      "name": текст_графы_1,
                      "format": текст_графы_Формат,
                      "primary_parent": текст_графы_Перв.примен.}
        """
        raw = "\n".join(f"[{k}]\n{v}" for k, v in regions.items())
        result = GostFields(raw_text=raw)

        desig_text = regions.get("designation", "")
        parent_text = regions.get("primary_parent", "")
        name_text = regions.get("name", "")
        format_text = regions.get("format", "")

        result.designation = self._first_designation(desig_text)
        result.primary_parent = self._first_designation(parent_text)
        result.name = self._clean_name(name_text)
        result.sheet_format = self._parse_format(format_text)

        # Остальные поля — по всему доступному тексту (если он передан)
        joined = "\n".join(regions.values())
        result.scale = self._parse_scale(joined)
        result.mass = self._parse_mass(joined)
        result.material = self._parse_material(joined)
        return result

    def _first_designation(self, text: str) -> str | None:
        if not text:
            return None
        m = self._RE_DESIGNATION.search(text)
        return self._format_designation(m) if m else None

    def _clean_name(self, text: str) -> str | None:
        """Собирает наименование из строк графы 1, отбрасывая служебные слова."""
        if not text:
            return None
        parts: list[str] = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            low = ln.lower().strip(".:-– ")
            if any(noise == low or noise in low for noise in self._STAMP_NOISE):
                continue
            if self._RE_DESIGNATION.search(ln):
                continue
            letters = sum(c.isalpha() for c in ln)
            if letters < 2:
                continue
            parts.append(ln)
        if not parts:
            return None
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    # ------------------------------------------------------------------
    # Запасной режим: разбор по всему тексту
    # ------------------------------------------------------------------
    def parse(self, text: str) -> GostFields:
        result = GostFields(raw_text=text)
        if not text or not text.strip():
            return result

        result.designation = self._parse_designation(text)
        result.scale = self._parse_scale(text)
        result.mass = self._parse_mass(text)
        result.material = self._parse_material(text)
        result.sheet_format = self._parse_format(text)
        result.name = self._parse_name(text, result)
        return result

    # ------------------------------------------------------------------
    def _format_designation(self, m: re.Match) -> str:
        code, groups, doc = m.group(1), m.group(2), m.group(3)
        groups = re.sub(r"\s*[.,]\s*", ".", groups.strip())
        designation = f"{code}.{groups}"
        if doc:
            designation += doc
        return designation

    def _parse_designation(self, text: str) -> str | None:
        m = self._RE_DESIGNATION.search(text)
        return self._format_designation(m) if m else None

    def _parse_scale(self, text: str) -> str | None:
        m = self._RE_SCALE_LABELED.search(text) or self._RE_SCALE_TOKEN.search(text)
        if not m:
            return None
        return re.sub(r"\s+", "", m.group(1)).replace(",", ".")

    def _parse_mass(self, text: str) -> str | None:
        m = self._RE_MASS.search(text)
        return m.group(1).replace(",", ".") if m else None

    def _parse_material(self, text: str) -> str | None:
        m = self._RE_MATERIAL.search(text)
        if not m:
            return None
        return re.sub(r"\s+", " ", m.group(1)).strip()

    def _parse_format(self, text: str) -> str | None:
        m = self._RE_FORMAT_LABELED.search(text) or self._RE_FORMAT.search(text)
        if not m:
            return None
        return m.group(1).upper().replace("A", "А")

    def _parse_name(self, text: str, parsed: GostFields) -> str | None:
        lines = [ln.strip() for ln in text.splitlines()]
        candidates: list[tuple[int, str]] = []

        designation_line = -1
        if parsed.designation:
            base = parsed.designation.split()[0]
            for i, ln in enumerate(lines):
                if base.replace(".", "") in ln.replace(".", "").replace(",", "").replace(" ", ""):
                    designation_line = i
                    break

        for i, ln in enumerate(lines):
            if not (3 <= len(ln) <= 60):
                continue
            low = ln.lower().strip(".:-– ")
            if any(noise in low for noise in self._STAMP_NOISE):
                continue
            if not re.fullmatch(r"[А-ЯЁа-яё][А-ЯЁа-яё0-9\s\-.,×xX/]*", ln):
                continue
            letters = sum(c.isalpha() for c in ln)
            if letters < len(ln) * 0.5:
                continue
            distance = abs(i - designation_line) if designation_line >= 0 else 9999
            candidates.append((distance, ln))

        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]
