"""Доступ к ресурсам приложения (иконки и т.п.), совместимый с PyInstaller.

При сборке в один файл PyInstaller распаковывает данные во временную папку и
кладёт её путь в `sys._MEIPASS`. В обычном запуске используем каталог проекта.
"""

import os
import sys

APP_NAME = "Электронный архив технической документации"
APP_TITLE = "ТехАрхив"


def resource_path(*parts: str) -> str:
    """Возвращает абсолютный путь к ресурсу как в dev-режиме, так и в .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def app_icon_path() -> str:
    return resource_path("assets", "app_icon.ico")
