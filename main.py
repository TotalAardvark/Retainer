import warnings
warnings.filterwarnings("ignore")

import sys
from PyQt6.QtWidgets import QApplication
from ui.tray_app import RetainerApp
from ui.assets import _resolve_brain_png_path
from PyQt6.QtGui import QIcon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Retainer")
    app.setWindowIcon(QIcon(_resolve_brain_png_path()))
    app.setQuitOnLastWindowClosed(False)

    tray = RetainerApp()
    tray.tray_icon.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
