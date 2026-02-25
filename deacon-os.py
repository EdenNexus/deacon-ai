import sys
import json
import os
import requests
import webbrowser
import ollama
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QLineEdit, QMessageBox, QFrame, QAbstractItemView, QTextEdit)
from PyQt5.QtCore import Qt

# ==========================================
# GLOBAL STATE & WIDGETS
# ==========================================
API_URL = "https://edennexus.in/deacon/api/data"
LOCAL_FILE = "projects_offline.json"
projects_data = []

main_window = None
project_list_widget = None
project_input_widget = None
ai_output_widget = None
status_label = None  # To show Online/Offline status

# ==========================================
# THEME: DARK MODE QSS
# ==========================================
DARK_THEME_QSS = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; font-family: 'Segoe UI', Arial, sans-serif; }
QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #555555; padding: 6px; border-radius: 4px; }
QPushButton:hover { background-color: #444444; border: 1px solid #777777; }
QPushButton:pressed { background-color: #222222; }
QLineEdit, QListWidget, QTextEdit { background-color: #252526; color: #ffffff; border: 1px solid #3e3e42; padding: 4px; border-radius: 4px; }
QListWidget::item:selected { background-color: #007acc; color: white; }
QLabel { color: #ffffff; }
QFrame[frameShape="4"] { color: #3e3e42; }
"""

# ==========================================
# DATA MANAGEMENT (OFFLINE/ONLINE MERGE)
# ==========================================
def load_local_data():
    """Reads the offline JSON file."""
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_local_data(data):
    """Saves data to the offline JSON file."""
    try:
        with open(LOCAL_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        QMessageBox.critical(main_window, "File Error", f"Could not save offline data:\n{str(e)}")

def merge_data(server_data, local_data):
    """Merges offline data into server data based on project names."""
    if not isinstance(server_data, list): server_data = []
    if not isinstance(local_data, list): local_data = []
    
    server_names = {p.get("name") for p in server_data if isinstance(p, dict)}
    
    merged = False
    for local_proj in local_data:
        if isinstance(local_proj, dict) and local_proj.get("name") not in server_names:
            server_data.append(local_proj)
            merged = True
            
    return server_data, merged

def load_data():
    """Attempts to fetch from API, falls back to offline, and merges if needed."""
    global projects_data
    
    status_label.setText("Status: 🔄 Syncing...")
    QApplication.processEvents()
    
    try:
        # Try to get server data (timeout of 3 seconds so it doesn't hang forever)
        response = requests.get(API_URL, timeout=3)
        response.raise_for_status()
        server_data = response.json()
        
        # We are online. Check for offline data to merge.
        local_data = load_local_data()
        projects_data, merged = merge_data(server_data, local_data)
        
        if merged:
            # If we had offline data to merge, push the combined list to the server immediately
            save_data(force_api_sync=True)
            # Clear the local file since it's safely on the server now
            if os.path.exists(LOCAL_FILE):
                os.remove(LOCAL_FILE)
                
        status_label.setText("Status: 🟢 Online (Synced)")
        
    except (requests.exceptions.RequestException, ValueError) as e:
        # We are offline (or API is broken). Load local data.
        projects_data = load_local_data()
        status_label.setText("Status: 🔴 Offline (Local Mode)")
    
    refresh_list()

def save_data(force_api_sync=False):
    """Attempts to save to API, falls back to local JSON if offline."""
    try:
        # Attempt to push to server
        response = requests.post(API_URL, json=projects_data, timeout=3)
        response.raise_for_status()
        status_label.setText("Status: 🟢 Online (Synced)")
        
        # Clean up local file if we successfully pushed to the server
        if os.path.exists(LOCAL_FILE):
            os.remove(LOCAL_FILE)
            
    except requests.exceptions.RequestException:
        # If it fails, save locally
        save_local_data(projects_data)
        status_label.setText("Status: 🔴 Offline (Saved Locally)")

def refresh_list():
    project_list_widget.clear()
    if isinstance(projects_data, list):
        for proj in projects_data:
            name = proj.get("name", "Unnamed Project")
            status = "✅" if proj.get("completed", False) else "⏳"
            project_list_widget.addItem(f"{status} | {name}")

def add_project():
    name = project_input_widget.text().strip()
    if not name: return
    projects_data.append({"name": name, "completed": False})
    project_input_widget.clear()
    save_data()
    refresh_list()

def toggle_status():
    current_row = project_list_widget.currentRow()
    if current_row < 0: return
    projects_data[current_row]["completed"] = not projects_data[current_row]["completed"]
    save_data()
    refresh_list()
    project_list_widget.setCurrentRow(current_row)

def delete_project():
    current_row = project_list_widget.currentRow()
    if current_row < 0: return
    del projects_data[current_row]
    save_data()
    refresh_list()

# ==========================================
# AI INTEGRATION (OLLAMA)
# ==========================================
def ask_ai_for_advice():
    pending_projects = [p['name'] for p in projects_data if isinstance(p, dict) and not p.get('completed', False)]
    if not pending_projects:
        ai_output_widget.setText("You have no pending projects! You're all caught up. 🎉")
        return

    ai_output_widget.setText("🤖 AI is analyzing your projects. Please wait...")
    QApplication.processEvents() 

    prompt = f"I am managing my tasks. Here are my current pending projects: {', '.join(pending_projects)}. Give me a very brief, encouraging 2-sentence tip on how to prioritize or tackle them today."

    try:
        response = ollama.chat(model='gemma3:4b', messages=[{'role': 'user', 'content': prompt}])
        ai_output_widget.setText(response['message']['content'])
    except Exception as e:
        ai_output_widget.setText(f"⚠️ Error contacting Ollama. Is it running locally?\nDetails: {str(e)}")

# ==========================================
# UI SETUP & INITIALIZATION
# ==========================================
def build_ui():
    global main_window, project_list_widget, project_input_widget, ai_output_widget, status_label

    main_window = QMainWindow()
    main_window.setWindowTitle("Workstation Dashboard AI (Offline Ready)")
    main_window.resize(850, 600)

    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)

    # --- LEFT PANEL: Quick Actions ---
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.setAlignment(Qt.AlignTop)

    qa_label = QLabel("⚡ Quick Actions")
    qa_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    left_layout.addWidget(qa_label)

    btn_browser = QPushButton("🌐 Open Browser")
    btn_browser.clicked.connect(lambda: webbrowser.open("https://google.com"))
    btn_calc = QPushButton("🧮 Calculator (Mock)")
    btn_notes = QPushButton("📝 Quick Note (Mock)")

    left_layout.addWidget(btn_browser)
    left_layout.addWidget(btn_calc)
    left_layout.addWidget(btn_notes)
    left_panel.setFixedWidth(200)

    # --- DIVIDER ---
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Sunken)

    # --- RIGHT PANEL: Project Management & AI ---
    right_panel = QWidget()
    right_layout = QVBoxLayout(right_panel)

    # Header & Status
    header_layout = QHBoxLayout()
    pm_label = QLabel("📂 Project Management")
    pm_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    
    status_label = QLabel("Status: Checking...")
    status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    status_label.setStyleSheet("color: #aaaaaa; font-style: italic;")
    
    header_layout.addWidget(pm_label)
    header_layout.addWidget(status_label)
    right_layout.addLayout(header_layout)

    # Inputs
    input_layout = QHBoxLayout()
    project_input_widget = QLineEdit()
    project_input_widget.setPlaceholderText("Enter new project name...")
    
    btn_add_project = QPushButton("➕ Add")
    btn_add_project.clicked.connect(add_project)
    
    btn_refresh = QPushButton("🔄 Sync")
    btn_refresh.clicked.connect(load_data)
    
    input_layout.addWidget(project_input_widget)
    input_layout.addWidget(btn_add_project)
    input_layout.addWidget(btn_refresh)
    right_layout.addLayout(input_layout)

    # List
    project_list_widget = QListWidget()
    project_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
    right_layout.addWidget(project_list_widget)

    # List Actions
    pm_actions_layout = QHBoxLayout()
    btn_toggle_status = QPushButton("Toggle Status (Done/Active)")
    btn_toggle_status.clicked.connect(toggle_status)
    btn_delete_project = QPushButton("Delete Selected")
    btn_delete_project.clicked.connect(delete_project)
    pm_actions_layout.addWidget(btn_toggle_status)
    pm_actions_layout.addWidget(btn_delete_project)
    right_layout.addLayout(pm_actions_layout)

    # --- AI ASSISTANT SECTION ---
    ai_label = QLabel("🤖 Local AI Project Assistant")
    ai_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 15px;")
    right_layout.addWidget(ai_label)

    btn_ask_ai = QPushButton("✨ Analyze Projects & Get Advice")
    btn_ask_ai.setStyleSheet("background-color: #007acc; color: white; font-weight: bold;")
    btn_ask_ai.clicked.connect(ask_ai_for_advice)
    right_layout.addWidget(btn_ask_ai)

    ai_output_widget = QTextEdit()
    ai_output_widget.setReadOnly(True)
    ai_output_widget.setFixedHeight(80)
    ai_output_widget.setPlaceholderText("AI insights will appear here...")
    right_layout.addWidget(ai_output_widget)

    # --- ASSEMBLE ---
    main_layout.addWidget(left_panel)
    main_layout.addWidget(divider)
    main_layout.addWidget(right_panel)

    return main_window

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME_QSS)
    
    window = build_ui()
    load_data() # Initial fetch/merge attempt
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()