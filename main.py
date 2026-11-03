import warnings
warnings.filterwarnings("ignore")

import sys
from PyQt6.QtWidgets import QApplication
from ui.tray_app import RetainerApp


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tray = RetainerApp()
    tray.tray_icon.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
