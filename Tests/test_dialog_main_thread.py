#!/usr/bin/env python3
"""
Test script demonstrating Dialog main thread integration.

This script shows how Dialog operations are automatically executed
in the main Qt thread, ensuring theme inheritance and proper UI integration.
"""

import sys
import threading
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QLabel,
)
from PySide6.QtCore import Qt
from Plugins_SDK.GeneralContext import Dialog


class TestWindow(QMainWindow):
    """Main window for testing Dialog integration."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dialog Main Thread Integration Test")
        self.setGeometry(100, 100, 400, 300)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Info label
        info = QLabel("Click buttons to test Dialog from main and background threads")
        layout.addWidget(info)

        # Test buttons
        btn_main = QPushButton("Test from Main Thread")
        btn_main.clicked.connect(self.test_main_thread)
        layout.addWidget(btn_main)

        btn_bg = QPushButton("Test from Background Thread")
        btn_bg.clicked.connect(self.test_background_thread)
        layout.addWidget(btn_bg)

        btn_progress = QPushButton("Test Progress Dialog")
        btn_progress.clicked.connect(self.test_progress)
        layout.addWidget(btn_progress)

        btn_question = QPushButton("Test Question Dialog")
        btn_question.clicked.connect(self.test_question)
        layout.addWidget(btn_question)

        # Dialog instance
        self.dialog = Dialog()

        # Status label
        self.status = QLabel("Ready")
        layout.addWidget(self.status)

    def test_main_thread(self):
        """Test Dialog from main thread."""
        self.status.setText("Testing from main thread...")
        self.dialog.msg_info(
            "Main Thread Test", "This dialog is created from the main thread"
        )
        self.status.setText("✓ Main thread test completed")

    def test_background_thread(self):
        """Test Dialog from background thread."""
        self.status.setText("Testing from background thread...")

        def background_work():
            time.sleep(0.5)
            # This will be automatically marshaled to the main thread
            self.dialog.msg_info(
                "Background Thread Test",
                "This dialog was created from a background thread\n"
                "but executed in the main thread!",
            )
            self.status.setText("✓ Background thread test completed")

        thread = threading.Thread(target=background_work, daemon=True)
        thread.start()

    def test_progress(self):
        """Test progress dialog."""
        self.status.setText("Testing progress dialog...")

        def progress_work():
            progress = self.dialog.progress(
                "Processing", "Simulating work...", maximum=100, cancelable=True
            )

            for i in range(101):
                if progress.canceled:
                    self.status.setText("✓ Progress canceled")
                    break
                progress.update(i, f"Processing {i}%")
                time.sleep(0.02)
            else:
                progress.close()
                self.status.setText("✓ Progress completed")

        thread = threading.Thread(target=progress_work, daemon=True)
        thread.start()

    def test_question(self):
        """Test question dialog."""
        self.status.setText("Testing question dialog...")

        def question_work():
            result = self.dialog.msg_question(
                "Confirm Action", "Do you want to proceed?"
            )
            if result:
                self.dialog.msg_info("Result", "You clicked Yes!")
                self.status.setText("✓ Question: Yes")
            else:
                self.dialog.msg_info("Result", "You clicked No!")
                self.status.setText("✓ Question: No")

        thread = threading.Thread(target=question_work, daemon=True)
        thread.start()


def main():
    """Run the test application."""
    app = QApplication(sys.argv)

    # Create and show main window
    window = TestWindow()
    window.show()

    print("=" * 60)
    print("Dialog Main Thread Integration Test")
    print("=" * 60)
    print("\nThis test demonstrates:")
    print("1. Dialog operations from the main thread")
    print("2. Dialog operations from background threads")
    print("3. Progress dialog with cancellation")
    print("4. Question dialogs with responses")
    print("\nAll dialogs inherit the application theme and are")
    print("properly integrated with the main window.")
    print("\n" + "=" * 60)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
