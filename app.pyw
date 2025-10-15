import sys
import os
import json
import subprocess
import requests
import zipfile
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime
import toml
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import urllib.request

# Fix DPI scaling before creating QApplication
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        
        # Set splash screen properties - slightly smaller
        self.setFixedSize(350, 250)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        
        # Create gradient background
        gradient = QLinearGradient(0, 0, 0, 250)
        gradient.setColorAt(0, QColor("#2d2d2d"))
        gradient.setColorAt(1, QColor("#1e1e1e"))
        
        # Create pixmap for splash
        pixmap = QPixmap(350, 250)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), gradient)
        
        # Add title - reduced font size and position
        title_font = QFont("Arial", 20, QFont.Bold)  # Reduced from 24 to 20
        painter.setFont(title_font)
        painter.setPen(QColor("#ff6b35"))  # Orange color
        
        # Draw title with smaller rect
        title_rect = QRect(0, 30, 350, 50)  # Reduced from (0, 40, 400, 60)
        painter.drawText(title_rect, Qt.AlignCenter, "Loading")
        
        # Add subtitle - also reduced
        subtitle_font = QFont("Arial", 11)  # Reduced from 12 to 11
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#cccccc"))
        
        subtitle_rect = QRect(0, 75, 350, 35)  # Adjusted for new size
        painter.drawText(subtitle_rect, Qt.AlignCenter, "Your Ultimate BeamMP Server Solution")
        
        painter.end()
        
        self.setPixmap(pixmap)
        
        # Progress bar setup
        self.progress = 0
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        
        # Rotation animation setup
        self.rotation_angle = 0
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.update_rotation)
        
        # Start animations
        self.progress_timer.start(30)
        self.rotation_timer.start(16)
        
    def update_progress(self):
        self.progress += 2
        if self.progress > 100:
            self.progress = 0
        self.repaint()
        
    def update_rotation(self):
        self.rotation_angle += 5
        if self.rotation_angle >= 360:
            self.rotation_angle = 0
        self.repaint()
        
    def drawContents(self, painter):
        super().drawContents(painter)
        
        # Draw spinning orange progress bar - adjusted for new size
        center_x = 175  # Changed from 200
        center_y = 180  # Changed from 220
        radius = 25     # Reduced from 30
        pen_width = 3   # Reduced from 4
        
        # Create gradient for the arc
        gradient = QConicalGradient(center_x, center_y, -self.rotation_angle)
        gradient.setColorAt(0, QColor("#ff6b35"))
        gradient.setColorAt(0.5, QColor("#ff8c42"))
        gradient.setColorAt(1, QColor("#ff6b35"))
        
        # Draw the spinning arc
        pen = QPen(gradient, pen_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        
        start_angle = self.rotation_angle * 16
        span_angle = 270 * 16
        painter.drawArc(center_x - radius, center_y - radius, 
                       radius * 2, radius * 2, start_angle, span_angle)
        
        # Draw inner circle
        painter.setPen(QPen(QColor("#3a3a3a"), 2))
        painter.setBrush(QBrush(QColor("#2d2d2d")))
        painter.drawEllipse(center_x - radius + pen_width, center_y - radius + pen_width,
                           (radius - pen_width) * 2, (radius - pen_width) * 2)
        
        # Draw progress text - adjusted position
        painter.setPen(QPen(QColor("#ff6b35")))
        font = QFont("Arial", 9, QFont.Bold)  # Reduced from 10 to 9
        painter.setFont(font)
        progress_text = f"{self.progress}%"
        text_rect = QRect(center_x - 15, center_y - 8, 30, 16)  # Adjusted size
        painter.drawText(text_rect, Qt.AlignCenter, progress_text)

class ServerManager(QMainWindow):
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    console_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.server_process = None
        self.server_folder = Path("BeamMP_Server")
        self.config_file = self.server_folder / "ServerConfig.toml"
        self.mods_folder = self.server_folder / "Resources"
        
        # Connect signals first
        self.console_message.connect(self._log_console_safe)
        self.server_started.connect(self._on_server_started)
        self.server_stopped.connect(self._on_server_stopped)
        
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        self.setWindowTitle("BeamMP Server Manager v2.3")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QGroupBox { 
                color: white; 
                border: 2px solid #3a3a3a; 
                border-radius: 5px; 
                margin-top: 10px; 
                font-weight: bold;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px 0 5px; 
            }
            QLabel { color: white; }
            QPushButton { 
                background-color: #2d2d2d; 
                color: white; 
                border: 1px solid #555; 
                padding: 8px 16px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3a3a3a; }
            QPushButton:pressed { background-color: #4a4a4a; }
            QPushButton:disabled { 
                background-color: #1a1a1a; 
                color: #666; 
                border-color: #333;
            }
            QLineEdit { 
                background-color: #2d2d2d; 
                color: white; 
                border: 1px solid #555; 
                padding: 5px; 
                border-radius: 3px;
            }
            QTextEdit { 
                background-color: #2d2d2d; 
                color: white; 
                border: 1px solid #555; 
                border-radius: 3px;
            }
            QSpinBox { 
                background-color: #2d2d2d; 
                color: white; 
                border: 1px solid #555; 
                padding: 5px; 
                border-radius: 3px;
            }
            QListWidget { 
                background-color: #2d2d2d; 
                color: white; 
                border: 1px solid #555; 
                border-radius: 3px;
            }
            QTabWidget::pane { border: 1px solid #555; }
            QTabBar::tab { 
                background-color: #2d2d2d; 
                color: white; 
                padding: 8px 16px; 
                margin-right: 2px;
            }
            QTabBar::tab:selected { background-color: #4a4a4a; }
            QTabBar::tab:hover { background-color: #3a3a3a; }
            QMessageBox { background-color: #2d2d2d; }
            QMessageBox QPushButton { background-color: #3a3a3a; }
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(400)
        
        # Server Status Group
        status_group = QGroupBox("Server Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        status_layout.addWidget(self.status_label)
        
        self.players_label = QLabel("Players: 0/0")
        status_layout.addWidget(self.players_label)
        
        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)
        
        # Server Controls Group
        controls_group = QGroupBox("Server Controls")
        controls_layout = QVBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Server")
        self.start_btn.clicked.connect(self.start_server)
        controls_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop Server")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        
        self.restart_btn = QPushButton("🔄 Restart Server")
        self.restart_btn.clicked.connect(self.restart_server)
        self.restart_btn.setEnabled(False)
        controls_layout.addWidget(self.restart_btn)
        
        controls_group.setLayout(controls_layout)
        left_layout.addWidget(controls_group)
        
        # Quick Actions Group
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout()
        
        self.download_btn = QPushButton("📥 Download Server")
        self.download_btn.clicked.connect(self.download_server)
        actions_layout.addWidget(self.download_btn)
        
        self.install_vc_btn = QPushButton("🔧 Install VC++ Redist")
        self.install_vc_btn.clicked.connect(self.install_vc_redist)
        actions_layout.addWidget(self.install_vc_btn)
        
        self.open_folder_btn = QPushButton("📁 Open Server Folder")
        self.open_folder_btn.clicked.connect(self.open_server_folder)
        actions_layout.addWidget(self.open_folder_btn)
        
        actions_group.setLayout(actions_layout)
        left_layout.addWidget(actions_group)
        
        # Server Info Group
        info_group = QGroupBox("Server Info")
        info_layout = QVBoxLayout()
        
        self.ip_label = QLabel("IP: 127.0.0.1")
        info_layout.addWidget(self.ip_label)
        
        self.port_label = QLabel("Port: 30814")
        info_layout.addWidget(self.port_label)
        
        self.uptime_label = QLabel("Uptime: 00:00:00")
        info_layout.addWidget(self.uptime_label)
        
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)
        
        left_layout.addStretch()
        
        # Create right panel for tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Configuration Tab
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        
        # Basic Settings
        basic_group = QGroupBox("Basic Settings")
        basic_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My BeamMP Server")
        basic_layout.addRow("Server Name:", self.name_input)
        
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(60)
        self.desc_input.setPlaceholderText("A cool BeamMP server")
        basic_layout.addRow("Description:", self.desc_input)
        
        self.auth_input = QLineEdit()
        self.auth_input.setEchoMode(QLineEdit.Password)
        self.auth_input.setPlaceholderText("Get from keymaster.beammp.com")
        basic_layout.addRow("Auth Key:", self.auth_input)
        
        self.map_input = QLineEdit()
        self.map_input.setPlaceholderText("/levels/gridmap_v2/info.json")
        basic_layout.addRow("Map:", self.map_input)
        
        basic_group.setLayout(basic_layout)
        config_layout.addWidget(basic_group)
        
        # Network Settings
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout()
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("0.0.0.0")
        network_layout.addRow("Bind IP:", self.ip_input)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(30814)
        network_layout.addRow("Port:", self.port_spin)
        
        self.max_players_spin = QSpinBox()
        self.max_players_spin.setRange(1, 100)
        self.max_players_spin.setValue(10)
        network_layout.addRow("Max Players:", self.max_players_spin)
        
        self.private_check = QCheckBox("Private Server")
        network_layout.addRow(self.private_check)
        
        network_group.setLayout(network_layout)
        config_layout.addWidget(network_group)
        
        # Game Settings
        game_group = QGroupBox("Game Settings")
        game_layout = QFormLayout()
        
        self.max_cars_spin = QSpinBox()
        self.max_cars_spin.setRange(1, 10)
        self.max_cars_spin.setValue(1)
        game_layout.addRow("Max Cars per Player:", self.max_cars_spin)
        
        self.debug_check = QCheckBox("Debug Mode")
        game_layout.addRow(self.debug_check)
        
        game_group.setLayout(game_layout)
        config_layout.addWidget(game_group)
        
        # Save button
        save_btn = QPushButton("💾 Save Configuration")
        save_btn.clicked.connect(self.save_config)
        config_layout.addWidget(save_btn)
        
        config_layout.addStretch()
        
        # Mods Tab
        mods_widget = QWidget()
        mods_layout = QVBoxLayout(mods_widget)
        
        # Mod Management
        mod_controls = QHBoxLayout()
        
        self.add_mod_btn = QPushButton("➕ Add Mod")
        self.add_mod_btn.clicked.connect(self.add_mod)
        mod_controls.addWidget(self.add_mod_btn)
        
        self.remove_mod_btn = QPushButton("➖ Remove Mod")
        self.remove_mod_btn.clicked.connect(self.remove_mod)
        mod_controls.addWidget(self.remove_mod_btn)
        
        self.refresh_mods_btn = QPushButton("🔄 Refresh")
        self.refresh_mods_btn.clicked.connect(self.refresh_mods)
        mod_controls.addWidget(self.refresh_mods_btn)
        
        mod_controls.addStretch()
        
        mods_layout.addLayout(mod_controls)
        
        # Mod List
        self.mod_list = QListWidget()
        self.mod_list.setSelectionMode(QListWidget.SingleSelection)
        mods_layout.addWidget(self.mod_list)
        
        # Console Tab
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Consolas", 9))
        console_layout.addWidget(self.console_output)
        
        # Console Input
        console_input_layout = QHBoxLayout()
        
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Enter command...")
        self.console_input.returnPressed.connect(self.send_console_command)
        console_input_layout.addWidget(self.console_input)
        
        self.send_cmd_btn = QPushButton("Send")
        self.send_cmd_btn.clicked.connect(self.send_console_command)
        console_input_layout.addWidget(self.send_cmd_btn)
        
        console_layout.addLayout(console_input_layout)
        
        # Add tabs
        self.tabs.addTab(config_widget, "⚙️ Configuration")
        self.tabs.addTab(mods_widget, "📦 Mods")
        self.tabs.addTab(console_widget, "🖥️ Console")
        
        right_layout.addWidget(self.tabs)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        
        # Initialize server folder
        self.server_folder.mkdir(exist_ok=True)
        self.mods_folder.mkdir(exist_ok=True)
        
        # Timer for updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)
        
        self.start_time = None
        
    # [Rest of the ServerManager methods remain the same as before]
    def download_server(self):
        """Download the latest BeamMP server"""
        self.log_console("Checking for latest BeamMP server...")
        self.download_btn.setEnabled(False)
        
        def download_worker():
            try:
                api_url = "https://api.github.com/repos/BeamMP/BeamMP-Server/releases/latest"
                response = requests.get(api_url, timeout=30)
                response.raise_for_status()
                
                release_data = response.json()
                download_url = None
                
                for asset in release_data["assets"]:
                    if asset["name"] == "BeamMP-Server.exe":
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    self.log_console("ERROR: Could not find Windows server executable")
                    return
                
                self.log_console(f"Downloading server...")
                server_exe = self.server_folder / "BeamMP-Server.exe"
                
                def download_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = min(100, (block_num * block_size * 100) // total_size)
                        if percent % 10 == 0:
                            self.log_console(f"Download progress: {percent}%")
                
                urllib.request.urlretrieve(download_url, server_exe, reporthook=download_progress)
                
                if server_exe.exists():
                    self.log_console("Server downloaded successfully!")
                    
                    try:
                        subprocess.run([str(server_exe)], cwd=str(self.server_folder), timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
                    
                    self.load_config()
                    self.log_console("Server ready to use!")
                    QMessageBox.information(self, "Success", "Server downloaded and initialized!")
                else:
                    self.log_console("ERROR: Download failed - file not found")
                    
            except Exception as e:
                self.log_console(f"Download error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to download server: {str(e)}")
            finally:
                self.download_btn.setEnabled(True)
        
        thread = threading.Thread(target=download_worker)
        thread.daemon = True
        thread.start()

    # [Include all the other methods from the previous version]
    def install_vc_redist(self):
        self.install_vc_btn.setEnabled(False)
        self.log_console("Downloading Visual C++ Redistributables...")
        
        def install_worker():
            try:
                vc_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
                vc_file = self.server_folder / "vc_redist.x64.exe"
                
                urllib.request.urlretrieve(vc_url, vc_file)
                self.log_console("Running VC++ installer...")
                
                result = subprocess.run([str(vc_file), "/quiet", "/norestart"], 
                                      capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    self.log_console("VC++ Redistributables installed!")
                    QMessageBox.information(self, "Success", "VC++ Redistributables installed!")
                else:
                    self.log_console(f"VC++ install returned code: {result.returncode}")
                    QMessageBox.warning(self, "Warning", "Installation may have failed. Try manual installation.")
                    
            except Exception as e:
                self.log_console(f"VC++ install error: {str(e)}")
                QMessageBox.warning(self, "Warning", f"Auto-install failed. Install manually from Microsoft.")
            finally:
                self.install_vc_btn.setEnabled(True)
        
        thread = threading.Thread(target=install_worker)
        thread.daemon = True
        thread.start()

    def load_config(self):
        try:
            if self.config_file.exists():
                config = toml.load(self.config_file)
                general = config.get("General", {})
                self.name_input.setText(general.get("Name", "BeamMP Server"))
                self.desc_input.setPlainText(general.get("Description", "A BeamMP server"))
                self.auth_input.setText(general.get("AuthKey", ""))
                self.map_input.setText(general.get("Map", "/levels/gridmap_v2/info.json"))
                ip = general.get("IP", "0.0.0.0")
                self.ip_input.setText(ip)
                self.port_spin.setValue(general.get("Port", 30814))
                self.max_players_spin.setValue(general.get("MaxPlayers", 10))
                self.max_cars_spin.setValue(general.get("MaxCars", 1))
                self.private_check.setChecked(general.get("Private", False))
                self.debug_check.setChecked(general.get("Debug", False))
                self.log_console("Configuration loaded successfully")
            else:
                self.log_console("No configuration file found. Using defaults.")
        except Exception as e:
            self.log_console(f"Error loading config: {str(e)}")

    def save_config(self):
        try:
            config = {
                "General": {
                    "AuthKey": self.auth_input.text().strip(),
                    "Debug": self.debug_check.isChecked(),
                    "Description": self.desc_input.toPlainText().strip(),
                    "Map": self.map_input.text().strip(),
                    "MaxCars": self.max_cars_spin.value(),
                    "MaxPlayers": self.max_players_spin.value(),
                    "Name": self.name_input.text().strip(),
                    "Port": self.port_spin.value(),
                    "Private": self.private_check.isChecked(),
                    "ResourceFolder": "Resources"
                }
            }
            ip_text = self.ip_input.text().strip()
            if ip_text and ip_text != "0.0.0.0":
                config["General"]["IP"] = ip_text
            with open(self.config_file, 'w') as f:
                toml.dump(config, f)
            self.log_console("Configuration saved successfully")
            QMessageBox.information(self, "Success", "Configuration saved!")
        except Exception as e:
            self.log_console(f"Error saving config: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")

    def start_server(self):
        try:
            server_exe = self.server_folder / "BeamMP-Server.exe"
            if not server_exe.exists():
                QMessageBox.warning(self, "Warning", "Server executable not found. Please download the server first.")
                return
            self.save_config()
            self.log_console("Starting BeamMP server...")
            self.server_process = subprocess.Popen(
                [str(server_exe)],
                cwd=str(self.server_folder),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.output_thread = threading.Thread(target=self.read_server_output)
            self.output_thread.daemon = True
            self.output_thread.start()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            self.start_time = time.time()
            self.log_console("Server process started!")
        except Exception as e:
            self.log_console(f"Error starting server: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to start server: {str(e)}")

    def stop_server(self):
        if not self.server_process:
            return
        self.log_console("Stopping server...")
        try:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log_console("Force killing server...")
                self.server_process.kill()
                self.server_process.wait()
            self.server_process = None
            self.start_time = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)
            self.log_console("Server stopped.")
        except Exception as e:
            self.log_console(f"Error stopping server: {str(e)}")

    def restart_server(self):
        self.log_console("Restarting server...")
        self.stop_server()
        QTimer.singleShot(1000, self.start_server)

    def read_server_output(self):
        try:
            while self.server_process and self.server_process.poll() is None:
                line = self.server_process.stdout.readline()
                if line:
                    self.console_message.emit(line.strip())
                if "Server started" in line or "Listening on port" in line:
                    self.server_started.emit()
        except Exception as e:
            self.console_message.emit(f"Error reading server output: {str(e)}")

    def _on_server_started(self):
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #51cf66;")

    def _on_server_stopped(self):
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")

    def send_console_command(self):
        command = self.console_input.text().strip()
        if command and self.server_process:
            try:
                self.log_console(f"> {command}")
                self.console_input.clear()
            except:
                self.log_console("Console commands not supported in this server version")

    def _log_console_safe(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_output.append(f"[{timestamp}] {message}")
        scrollbar = self.console_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log_console(self, message):
        self.console_message.emit(message)

    def add_mod(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Mod File", "", 
            "Zip Files (*.zip);;All Files (*.*)"
        )
        if file_path:
            try:
                mod_name = Path(file_path).name
                dest_path = self.mods_folder / mod_name
                if dest_path.exists():
                    reply = QMessageBox.question(self, "Mod Exists", 
                                               f"Mod '{mod_name}' already exists. Overwrite?",
                                               QMessageBox.Yes | QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
                shutil.copy2(file_path, dest_path)
                self.log_console(f"Added mod: {mod_name}")
                self.refresh_mods()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add mod: {str(e)}")

    def remove_mod(self):
        current_item = self.mod_list.currentItem()
        if current_item:
            try:
                mod_name = current_item.text()
                mod_path = self.mods_folder / mod_name
                reply = QMessageBox.question(self, "Confirm Remove", 
                                           f"Remove mod '{mod_name}'?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    if mod_path.exists():
                        mod_path.unlink()
                        self.log_console(f"Removed mod: {mod_name}")
                        self.refresh_mods()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove mod: {str(e)}")

    def refresh_mods(self):
        self.mod_list.clear()
        try:
            if self.mods_folder.exists():
                for mod_file in self.mods_folder.glob("*.zip"):
                    self.mod_list.addItem(mod_file.name)
                mod_count = len(list(self.mods_folder.glob("*.zip")))
                self.log_console(f"Refreshed mods list - {mod_count} mods found")
        except Exception as e:
            self.log_console(f"Error refreshing mods: {str(e)}")

    def open_server_folder(self):
        try:
            os.startfile(str(self.server_folder))
        except:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.server_folder)))

    def update_status(self):
        try:
            if self.server_process and self.server_process.poll() is None:
                self.status_label.setText("Status: Running")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #51cf66;")
                if self.start_time:
                    uptime = int(time.time() - self.start_time)
                    hours = uptime // 3600
                    minutes = (uptime % 3600) // 60
                    seconds = uptime % 60
                    self.uptime_label.setText(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")
                self.ip_label.setText(f"IP: {self.ip_input.text() or '127.0.0.1'}")
                self.port_label.setText(f"Port: {self.port_spin.value()}")
            else:
                if self.server_process:
                    self.server_process = None
                    self.start_btn.setEnabled(True)
                    self.stop_btn.setEnabled(False)
                    self.restart_btn.setEnabled(False)
                    self.start_time = None
                    self.server_stopped.emit()
                self.uptime_label.setText("Uptime: 00:00:00")
        except Exception as e:
            pass

    def closeEvent(self, event):
        if self.server_process:
            reply = QMessageBox.question(
                self, "Server Running",
                "Server is still running. Stop it before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.stop_server()
                QTimer.singleShot(2000, event.accept)
            elif reply == QMessageBox.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Create and show splash screen
    splash = SplashScreen()
    splash.show()
    
    # Process events to show splash immediately
    app.processEvents()
    
    # Create main window (but don't show it yet)
    manager = ServerManager()
    
    # Simulate loading time with splash screen
    def show_main_window():
        splash.close()
        manager.show()
        
    # Show main window after 1.5 seconds
    QTimer.singleShot(1500, show_main_window)
    
    sys.exit(app.exec_())

# test comment to test workfow [3]

if __name__ == '__main__':

    main()


