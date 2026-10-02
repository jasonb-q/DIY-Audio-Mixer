from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QPushButton, QComboBox,
    QVBoxLayout, QLabel, QGroupBox, QProgressBar,
    QSystemTrayIcon, QMenu, QStyle
)
from PyQt6.QtCore import QSize, QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction
import sys
import subprocess
import serial
import json


STYLESHEET = """
    QMainWindow {
        background: #1e1e2e;
    }
    QWidget {
        color: #cdd6f4;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #313244;
        border-radius: 8px;
        margin-top: 10px;
        padding: 10px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: #89b4fa;
    }
    QComboBox, QPushButton {
        background: #313244;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 6px 10px;
    }
    QComboBox:hover, QPushButton:hover {
        background: #45475a;
    }
    QComboBox QAbstractItemView {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        outline: none;
        selection-background-color: #89b4fa;
        selection-color: #1e1e2e;
    }
    QPushButton {
        font-weight: bold;
    }
    QProgressBar {
        border: none;
        border-radius: 4px;
        background: #313244;
        text-align: center;
        height: 16px;
    }
    QProgressBar::chunk {
        background-color: #89b4fa;
        border-radius: 4px;
    }
"""


class SliderWidget(QWidget):
    def __init__(self, name, sid, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.sid = sid

        self.combo = QComboBox()
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(True)
        self.level.setFormat("%v%")

        group_layout = QVBoxLayout()
        group_layout.addWidget(self.combo)
        group_layout.addWidget(self.level)

        self.group = QGroupBox(self.name)
        self.group.setLayout(group_layout)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.group)
        self.setLayout(outer_layout)

    def refresh(self):
        current_sid = self.combo.currentData()
        self.combo.clear()
        self.combo.addItem("None", None)
        restore_index = 0
        for name, sid in get_streams():
            self.combo.addItem(name, sid)
            if sid == current_sid:
                restore_index = self.combo.count() - 1
        self.combo.setCurrentIndex(restore_index)

    def set_level(self, value):
        self.level.setValue(value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Mixer")
        self.setMinimumSize(QSize(380, 440))
        self.last_val = [0, 0, 0, 0]

        self.page_layout = QVBoxLayout()
        self.page_layout.setContentsMargins(16, 16, 16, 16)
        self.page_layout.setSpacing(12)

        self.sld1 = SliderWidget("Channel 1", "sld1")
        self.sld2 = SliderWidget("Channel 2", "sld2")
        self.sld3 = SliderWidget("Channel 3", "sld3")

        self.sld1.refresh()
        self.sld2.refresh()
        self.sld3.refresh()

        self.page_layout.addWidget(self.sld1)
        self.page_layout.addWidget(self.sld2)
        self.page_layout.addWidget(self.sld3)

        self.master_level = QProgressBar()
        self.master_level.setRange(0, 100)
        self.master_level.setTextVisible(True)
        self.master_level.setFormat("%v%")

        master_layout = QVBoxLayout()
        master_layout.addWidget(self.master_level)

        self.master_group = QGroupBox("Master Volume")
        self.master_group.setLayout(master_layout)
        self.page_layout.addWidget(self.master_group)

        self.ref_but = QPushButton("Refresh Streams")
        self.ref_but.clicked.connect(self.refresh_sliders)
        self.page_layout.addWidget(self.ref_but)

        self.status_label = QLabel("● Connecting...")
        self.status_label.setStyleSheet("color: #f9e2af;")
        self.page_layout.addWidget(self.status_label)

        self.serial_thread = QThread()
        self.worker = SerialWorker("/dev/ttyUSB0")
        self.worker.moveToThread(self.serial_thread)

        self.serial_thread.started.connect(self.worker.run)
        self.worker.volumes_received.connect(self.update_volumes)
        self.worker.error.connect(self.handle_error)

        self.serial_thread.start()
        self.status_label.setText("● Connected")
        self.status_label.setStyleSheet("color: #a6e3a1;")

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(3000)
        self.refresh_timer.timeout.connect(self.refresh_sliders)
        self.refresh_timer.start()

        self.widget = QWidget()
        self.widget.setLayout(self.page_layout)
        self.setCentralWidget(self.widget)

        self.setup_tray()

    def setup_tray(self):
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        self.setWindowIcon(icon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Audio Mixer")

        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def changeEvent(self, a0):
        if a0.type() == a0.Type.WindowStateChange and self.isMinimized():
            self.hide()
        super().changeEvent(a0)

    def closeEvent(self, a0):
        a0.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Audio Mixer",
            "Still running in the background. Use the tray icon to quit.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
            )

    def quit_app(self):
        self.refresh_timer.stop()
        self.worker.stop()
        self.serial_thread.quit()
        self.serial_thread.wait()
        self.tray_icon.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def refresh_sliders(self):
        self.sld1.refresh()
        self.sld2.refresh()
        self.sld3.refresh()

    def handle_error(self, message):
        self.status_label.setText(f"● Error: {message}")
        self.status_label.setStyleSheet("color: #f38ba8;")

    @pyqtSlot(int, int, int, int)
    def update_volumes(self, pot1, pot2, pot3, pot4):
        sld1_data = self.sld1.combo.currentData()
        sld2_data = self.sld2.combo.currentData()
        sld3_data = self.sld3.combo.currentData()

        self.sld1.set_level(pot1)
        self.sld2.set_level(pot2)
        self.sld3.set_level(pot3)
        self.master_level.setValue(pot4)

        if abs(pot1 - self.last_val[0]) > 2 and self.sld1.combo.currentText() != "None":
            subprocess.Popen([
                "wpctl",
                "set-volume",
                str(sld1_data),
                f"{pot1}%"
                ])
            self.last_val[0] = pot1

        if abs(pot2 - self.last_val[1]) > 2 and self.sld2.combo.currentText() != "None":
            subprocess.Popen([
                "wpctl",
                "set-volume",
                str(sld2_data),
                f"{pot2}%"
                ])
            self.last_val[1] = pot2

        if abs(pot3 - self.last_val[2]) > 2 and self.sld3.combo.currentText() != "None":
            subprocess.Popen([
                "wpctl",
                "set-volume",
                str(sld3_data),
                f"{pot3}%"
                ])
            self.last_val[2] = pot3

        if abs(pot4 - self.last_val[3]) > 2:
            subprocess.Popen([
                "wpctl",
                "set-volume",
                "@DEFAULT_AUDIO_SINK@",
                f"{pot4}%"
                ])
            self.last_val[3] = pot4


class SerialWorker(QObject):
    volumes_received = pyqtSignal(int, int, int, int)
    error = pyqtSignal(str)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True

    @pyqtSlot()
    def run(self):
        try:
            ser = serial.Serial(
                    self.port,
                    115200,
                    timeout=0.1
                    )

            while self.running:
                line = ser.readline().decode("utf-8", errors="ignore").strip()

                if not line:
                    continue

                try:
                    pot1, pot2, pot3, pot4 = line.split(",")
                    pot1 = int(pot1)
                    pot2 = int(pot2)
                    pot3 = int(pot3)
                    pot4 = int(pot4)

                    self.volumes_received.emit(pot1, pot2, pot3, pot4)
                except (ValueError, IndexError):
                    continue

            ser.close()
        except Exception as e:
            self.error.emit(str(e))
    def stop(self):
        self.running = False


def get_streams():
    streams = []
    results = subprocess.run(
            ["pw-dump"],
            text=True,
            capture_output=True,
            check=True
            )
    objects = json.loads(results.stdout)
    for obj in objects:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        info = obj.get("info", {})
        props = info.get("props", {})
        if props.get("media.class") == "Stream/Output/Audio":
            app_name = props.get("application.name")
            sid = obj["id"]
            streams.append((app_name, sid))
    return streams

if __name__ == "__main__":
    get_streams()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    app.exec()
