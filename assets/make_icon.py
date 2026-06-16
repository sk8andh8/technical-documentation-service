"""Генерирует иконку приложения «ТехАрхив» (assets/app_icon.ico + .png).

Запуск: python assets/make_icon.py
Иконка рисуется программно (PIL), без внешних файлов: синий чертёжный лист
со штампом и буквой «Т» — отсылка к техническому архиву.
"""

import os

from PIL import Image, ImageDraw

SIZE = 256
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

BG = (37, 99, 235)        # синий (#2563EB)
BG2 = (29, 78, 216)       # тёмно-синий (#1D4ED8)
SHEET = (248, 250, 252)   # почти белый лист
LINE = (148, 163, 184)    # серые линии штампа
ACCENT = (37, 99, 235)


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Фон со скруглением (диагональный переход имитируем двумя прямоугольниками)
    _rounded(d, (8, 8, SIZE - 8, SIZE - 8), 48, BG)
    d.polygon([(8, SIZE - 8), (SIZE - 8, SIZE - 8), (SIZE - 8, 120)], fill=BG2)
    _rounded(d, (8, 8, SIZE - 8, SIZE - 8), 48, None)

    # Чертёжный лист
    sheet_box = (60, 44, 196, 212)
    _rounded(d, sheet_box, 10, SHEET)

    # Линии штампа снизу листа (основная надпись)
    for y in (172, 186, 200):
        d.line((72, y, 184, y), fill=LINE, width=2)
    d.line((140, 160, 140, 212), fill=LINE, width=2)
    d.rectangle((72, 160, 184, 212), outline=LINE, width=2)

    # Буква «Т» — технический архив
    d.rectangle((92, 70, 164, 80), fill=ACCENT)       # перекладина
    d.rectangle((123, 70, 133, 138), fill=ACCENT)     # ножка

    return img


def main():
    img = build()
    png_path = os.path.join(OUT_DIR, "app_icon.png")
    ico_path = os.path.join(OUT_DIR, "app_icon.ico")
    img.save(png_path)
    img.save(
        ico_path,
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("written:", png_path)
    print("written:", ico_path)


if __name__ == "__main__":
    main()
