import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class MaFenetre(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Mon App PySide6")
        self.setFixedSize(300, 200)

        # Widgets
        self.label = QLabel("Entrez votre nom :")
        self.input = QLineEdit()
        self.button = QPushButton("Dire Bonjour")
        self.output_label = QLabel("")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.button)
        layout.addWidget(self.output_label)
        self.setLayout(layout)

        # Connexion du bouton
        self.button.clicked.connect(self.dire_bonjour)

    def dire_bonjour(self):
        nom = self.input.text().strip()
        if nom:
            self.output_label.setText(f"Bonjour, {nom} !")
        else:
            self.output_label.setText("Veuillez entrer un nom.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = MaFenetre()
    fenetre.show()
    sys.exit(app.exec())
