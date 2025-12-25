# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
