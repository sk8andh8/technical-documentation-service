import os
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon

from database import Base, engine, ensure_schema
from resources import APP_NAME, app_icon_path
from ui.main_window import MainWindow


def main():
    # Автоматически создаем таблицы в локальном Postgres при первом запуске
    Base.metadata.create_all(bind=engine)
    # Идемпотентно дотягиваем схему на существующих базах (колонка designation)
    ensure_schema()

    # Инициализация Qt инвайронмента
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    # Иконка приложения (если ресурс доступен)
    icon_path = app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Устанавливаем Fusion стиль для современного вида
    app.setStyle("Fusion")

    # Цветовая палитра
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F8FAFC"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1E293B"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F1F5F9"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1E293B"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#F1F5F9"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1E293B"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3B82F6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    # Запуск основного интерфейса
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
