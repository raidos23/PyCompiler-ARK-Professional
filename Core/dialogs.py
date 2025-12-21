# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
Dialogues personnalisés pour PyCompiler ARK++.
Inclut ProgressDialog, boîtes de message, et autres dialogues spécifiques.
"""

# À compléter avec les classes de dialogues personnalisés
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    def __init__(self, title="Progression", parent=None, cancelable=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Non modale pour ne pas bloquer l'UI
        self.setMinimumWidth(400)
        self._canceled = False
        layout = QVBoxLayout(self)
        self.label = QLabel("Préparation...", self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)  # Indéterminé au début
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        if cancelable:
            btn_row = QHBoxLayout()
            btn_cancel = QPushButton("Annuler", self)
            btn_cancel.clicked.connect(self._on_cancel)
            btn_row.addStretch(1)
            btn_row.addWidget(btn_cancel)
            layout.addLayout(btn_row)
        self.setLayout(layout)

    def set_message(self, msg):
        self.label.setText(msg)
        QApplication.processEvents()

    def set_progress(self, value, maximum=None):
        if maximum is not None:
            self.progress.setMaximum(maximum)
        self.progress.setValue(value)
        QApplication.processEvents()

    def _on_cancel(self):
        self._canceled = True
        try:
            self.close()
        except Exception:
            pass

    def is_canceled(self):
        return self._canceled


class CompilationProcessDialog(QDialog):
    """Dialog simple pour afficher le chargement du workspace."""
    
    def __init__(self, title="Chargement", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        
        layout = QVBoxLayout(self)
        
        # Statut
        self.status_label = QLabel("Initialisation...", self)
        layout.addWidget(self.status_label)
        
        # Barre de progression
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        
        # Boutons
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Annuler", self)
        self.btn_close = QPushButton("Fermer", self)
        self.btn_close.setEnabled(False)
        
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)
        
        self.setLayout(layout)
    
    def set_status(self, status_text):
        """Mettre à jour le statut."""
        self.status_label.setText(status_text)
        QApplication.processEvents()
    
    def set_progress(self, value, maximum=None):
        """Mettre à jour la barre de progression."""
        if maximum is not None:
            self.progress.setMaximum(maximum)
        self.progress.setValue(value)
        QApplication.processEvents()
