#Prototypage du système de Dialog pour Plugins


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
)
from PySide6.QtCore import Qt

class Dialog(QDialog):
    """
    Dialog ARK++  pour plugins BCASL / ACASL
    Supporte :
    - OK / Annuler / Oui / Non / Custom buttons
    - Logs dynamiques
    - Callbacks
    """

    def __init__(self, title="ARK++ Dialog", width=500, height=400, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(width, height)

        # Layout principal vertical
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Label d’instructions/messages
        self.label = QLabel("Message")
        self.layout.addWidget(self.label)

        # Zone de texte pour logs dynamiques
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.layout.addWidget(self.text_area)

        # Layout pour boutons
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        # Boutons standards
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Annuler")
        self.yes_button = QPushButton("Oui")
        self.no_button = QPushButton("Non")

        # Connexion aux méthodes internes
        self.ok_button.clicked.connect(lambda: self._handle_response("ok"))
        self.cancel_button.clicked.connect(lambda: self._handle_response("cancel"))
        self.yes_button.clicked.connect(lambda: self._handle_response("yes"))
        self.no_button.clicked.connect(lambda: self._handle_response("no"))

        # Dict pour callbacks personnalisés
        self.callbacks = {}

        # Stocke la réponse
        self.response = None

        # Ajouter boutons OK et Annuler par défaut
        self.add_buttons(["ok", "cancel"])

    # -----------------------
    # Méthodes publiques
    # -----------------------

    def add_buttons(self, buttons: list):
        """Ajouter des boutons par noms : ok, cancel, yes, no, custom:<label>"""
        for btn_name in buttons:
            if btn_name == "ok":
                self.button_layout.addWidget(self.ok_button)
            elif btn_name == "cancel":
                self.button_layout.addWidget(self.cancel_button)
            elif btn_name == "yes":
                self.button_layout.addWidget(self.yes_button)
            elif btn_name == "no":
                self.button_layout.addWidget(self.no_button)
            elif btn_name.startswith("custom:"):
                label = btn_name.split(":", 1)[1]
                btn = QPushButton(label)
                btn.clicked.connect(lambda _, l=label: self._handle_response(l))
                self.button_layout.addWidget(btn)

    def set_label(self, text: str):
        self.label.setText(text)

    def log(self, message: str):
        self.text_area.append(message)

    def clear_log(self):
        self.text_area.clear()

    def set_callback(self, button_name: str, func):
        """Associer un callback à un bouton"""
        self.callbacks[button_name] = func

    # -----------------------
    # Méthodes internes
    # -----------------------
    def _handle_response(self, resp):
        self.response = resp
        if resp in self.callbacks:
            try:
                self.callbacks[resp]()
            except Exception as e:
                self.log(f"Erreur callback {resp}: {e}")
        self.close()