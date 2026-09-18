import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Litenova")
        self.resize(1200, 750)

        label = QLabel("Litenova")
        label.setStyleSheet("font-size: 32px;")
        self.setCentralWidget(label)


app = QApplication(sys.argv)

window = MainWindow()
window.show()

sys.exit(app.exec())