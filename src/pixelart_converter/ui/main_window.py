from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """Empty main window. Conversion controls are added in later tasks."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("pixelart-converter")
        self.resize(960, 640)
