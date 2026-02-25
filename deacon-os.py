import sys
import json
import os
import requests
import webbrowser
import ollama
import subprocess
import platform
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QLineEdit, QMessageBox, QFrame, QAbstractItemView, QTextEdit)
from PyQt5.QtCore import Qt

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# Edit these values to customize your app
# ==========================================
CONFIG = {
    # --- App Window Settings ---
    "APP_TITLE": "Workstation AI Assistant",
    "WINDOW_WIDTH": 950,
    "WINDOW_HEIGHT": 650,
    
    # --- Network & Data Settings ---
    "API_URL": "https://edennexus.in/deacon/api/data",
    "LOCAL_FILE": "projects_offline.json",
    "NETWORK_TIMEOUT": 3,  # How many seconds to wait before switching to offline mode
    
    # --- Local AI (Ollama) Models ---
    # You can change these to 'llama3', 'mistral', or your specific local models
    "AI_MODEL_ESTIMATES": "gpt-oss:120b-cloud",
    "AI_MODEL_BREAKDOWN": "gpt-oss:120b-cloud",
    "AI_MODEL_COMMANDS": "gpt-oss:120b-cloud",
    "AI_MODEL_REPORTS": "gpt-oss:120b-cloud",
    
    # --- UI Styling (Dark Theme QSS) ---
    "THEME_QSS": """
        QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; font-family: 'Segoe UI', Arial, sans-serif; }
        QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #555555; padding: 6px; border-radius: 4px; }
        QPushButton:hover { background-color: #444444; border: 1px solid #777777; }
        QPushButton:pressed { background-color: #222222; }
        QLineEdit, QListWidget, QTextEdit { background-color: #252526; color: #ffffff; border: 1px solid #3e3e42; padding: 4px; border-radius: 4px; }
        QListWidget::item:selected { background-color: #007acc; color: white; }
        QLabel { color: #ffffff; }
        QFrame[frameShape="4"] { color: #3e3e42; }
    """
}

# ==========================================
# GLOBAL STATE & WIDGETS
# ==========================================
projects_data = []

main_window = None
project_list_widget = None
project_input_widget = None
ai_output_widget = None
status_label = None
ai_cmd_input = None

# ==========================================
# DATA MANAGEMENT (OFFLINE/ONLINE MERGE)
# ==========================================
def load_local_data():
    if os.path.exists(CONFIG["LOCAL_FILE"]):
        try:
            with open(CONFIG["LOCAL_FILE"], 'r') as f: return json.load(f)
        except Exception: return []
    return []

def save_local_data(data):
    try:
        with open(CONFIG["LOCAL_FILE"], 'w') as f: json.dump(data, f, indent=4)
    except Exception as e:
        QMessageBox.critical(main_window, "File Error", f"Could not save offline data:\n{str(e)}")

def merge_data(server_data, local_data):
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
    global projects_data
    status_label.setText("Status: 🔄 Syncing...")
    QApplication.processEvents()
    try:
        response = requests.get(CONFIG["API_URL"], timeout=CONFIG["NETWORK_TIMEOUT"])
        response.raise_for_status()
        server_data = response.json()
        local_data = load_local_data()
        projects_data, merged = merge_data(server_data, local_data)
        if merged:
            save_data(force_api_sync=True)
            if os.path.exists(CONFIG["LOCAL_FILE"]): os.remove(CONFIG["LOCAL_FILE"])
        status_label.setText("Status: 🟢 Online (Synced)")
    except (requests.exceptions.RequestException, ValueError):
        projects_data = load_local_data()
        status_label.setText("Status: 🔴 Offline (Local Mode)")
    refresh_list()

def save_data(force_api_sync=False):
    try:
        response = requests.post(CONFIG["API_URL"], json=projects_data, timeout=CONFIG["NETWORK_TIMEOUT"])
        response.raise_for_status()
        status_label.setText("Status: 🟢 Online (Synced)")
        if os.path.exists(CONFIG["LOCAL_FILE"]): os.remove(CONFIG["LOCAL_FILE"])
    except requests.exceptions.RequestException:
        save_local_data(projects_data)
        status_label.setText("Status: 🔴 Offline (Saved Locally)")

def refresh_list():
    project_list_widget.clear()
    if isinstance(projects_data, list):
        for proj in projects_data:
            name = proj.get("name", "Unnamed Project")
            status = "✅" if proj.get("completed", False) else "⏳"
            project_list_widget.addItem(f"{status} | {name}")

# ==========================================
# CORE FEATURES & AI PROJECT MANAGEMENT
# ==========================================
def add_project():
    name = project_input_widget.text().strip()
    if not name: return
    
    project_input_widget.setText("🤖 Estimating time...")
    project_input_widget.setEnabled(False)
    QApplication.processEvents()

    try:
        prompt = f"Estimate the time to complete this task: '{name}'. Respond ONLY with the time estimate in brackets, like [~2 hours] or [~30 mins]. Do not add any other text."
        response = ollama.chat(model=CONFIG["AI_MODEL_ESTIMATES"], messages=[{'role': 'user', 'content': prompt}])
        estimate = response['message']['content'].strip()
        final_name = f"{name} {estimate}"
    except Exception:
        final_name = name 
        
    projects_data.append({"name": final_name, "completed": False})
    
    project_input_widget.setEnabled(True)
    project_input_widget.clear()
    save_data()
    refresh_list()

def break_down_project():
    current_row = project_list_widget.currentRow()
    if current_row < 0:
        QMessageBox.warning(main_window, "Warning", "Select a project to break down.")
        return
        
    parent_task = projects_data[current_row]["name"]
    ai_output_widget.setText(f"🤖 Breaking down '{parent_task}' into sub-tasks...")
    QApplication.processEvents()

    try:
        prompt = f"Break down the task '{parent_task}' into 3 or 4 actionable sub-tasks. Respond ONLY with a comma-separated list of the sub-tasks. No bullet points, no numbers, no intro text."
        response = ollama.chat(model=CONFIG["AI_MODEL_BREAKDOWN"], messages=[{'role': 'user', 'content': prompt}])
        
        sub_tasks = [task.strip() for task in response['message']['content'].split(',') if task.strip()]
        
        if sub_tasks:
            del projects_data[current_row]
            for st in sub_tasks:
                projects_data.append({"name": st, "completed": False})
                
            ai_output_widget.setText(f"✅ Successfully broke down task into {len(sub_tasks)} sub-tasks.")
            save_data()
            refresh_list()
    except Exception as e:
        ai_output_widget.setText(f"⚠️ Failed to break down task: {str(e)}")

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
# AI REPORTING & SYSTEM COMMANDS
# ==========================================
def generate_daily_report():
    completed = [p['name'] for p in projects_data if p.get('completed', True)]
    pending = [p['name'] for p in projects_data if not p.get('completed', False)]
    
    ai_output_widget.setText("🤖 Generating your daily standup report...")
    QApplication.processEvents() 

    prompt = f"""Write a brief, professional end-of-day standup report. 
    Completed today: {', '.join(completed) if completed else 'None'}. 
    Pending for tomorrow: {', '.join(pending) if pending else 'None'}.
    Keep it concise, encouraging, and ready to be pasted into a team chat."""

    try:
        response = ollama.chat(model=CONFIG["AI_MODEL_REPORTS"], messages=[{'role': 'user', 'content': prompt}])
        ai_output_widget.setText(response['message']['content'])
    except Exception as e:
        ai_output_widget.setText(f"⚠️ Error generating report: {str(e)}")

def execute_ai_command():
    intent = ai_cmd_input.text().strip()
    if not intent: return
    
    ai_cmd_input.setText("🤖 Translating...")
    ai_cmd_input.setEnabled(False)
    QApplication.processEvents()

    os_name = platform.system()
    prompt = f"Translate this intent into a single terminal command for {os_name}: '{intent}'. Respond ONLY with the raw command, nothing else. No markdown formatting, no explanations."

    try:
        response = ollama.chat(model=CONFIG["AI_MODEL_COMMANDS"], messages=[{'role': 'user', 'content': prompt}])
        command = response['message']['content'].strip()
        command = command.replace("`", "")
        
        subprocess.Popen(command, shell=True)
        ai_output_widget.setText(f"🚀 Executed system command: {command}")
    except Exception as e:
        ai_output_widget.setText(f"⚠️ Failed to execute command: {str(e)}")
    
    ai_cmd_input.clear()
    ai_cmd_input.setEnabled(True)

# ==========================================
# UI SETUP & INITIALIZATION
# ==========================================
def build_ui():
    global main_window, project_list_widget, project_input_widget, ai_output_widget, status_label, ai_cmd_input

    main_window = QMainWindow()
    main_window.setWindowTitle(CONFIG["APP_TITLE"])
    main_window.resize(CONFIG["WINDOW_WIDTH"], CONFIG["WINDOW_HEIGHT"])

    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)

    # --- LEFT PANEL ---
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.setAlignment(Qt.AlignTop)

    qa_label = QLabel("⚡ Quick Actions")
    qa_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    left_layout.addWidget(qa_label)

    btn_browser = QPushButton("🌐 Open Browser")
    btn_browser.clicked.connect(lambda: webbrowser.open("https://google.com"))
    left_layout.addWidget(btn_browser)
    
    ai_cmd_label = QLabel("🪄 AI System Command:")
    ai_cmd_label.setStyleSheet("margin-top: 15px; color: #aaaaaa;")
    left_layout.addWidget(ai_cmd_label)
    
    ai_cmd_input = QLineEdit()
    ai_cmd_input.setPlaceholderText("e.g., open notepad")
    ai_cmd_input.returnPressed.connect(execute_ai_command)
    left_layout.addWidget(ai_cmd_input)
    
    btn_ai_cmd = QPushButton("Execute Intent")
    btn_ai_cmd.clicked.connect(execute_ai_command)
    left_layout.addWidget(btn_ai_cmd)

    left_panel.setFixedWidth(220)

    # --- DIVIDER ---
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Sunken)

    # --- RIGHT PANEL ---
    right_panel = QWidget()
    right_layout = QVBoxLayout(right_panel)

    # Header
    header_layout = QHBoxLayout()
    pm_label = QLabel("📂 AI Project Manager")
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
    project_input_widget.setPlaceholderText("Enter new project... (AI will estimate time)")
    project_input_widget.returnPressed.connect(add_project)
    
    btn_add_project = QPushButton("➕ Add Task")
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
    btn_toggle_status = QPushButton("Toggle Status")
    btn_toggle_status.clicked.connect(toggle_status)
    
    btn_breakdown = QPushButton("✂️ Break Down with AI")
    btn_breakdown.setStyleSheet("background-color: #6a0dad; color: white;")
    btn_breakdown.clicked.connect(break_down_project)
    
    btn_delete_project = QPushButton("Delete Selected")
    btn_delete_project.clicked.connect(delete_project)
    
    pm_actions_layout.addWidget(btn_toggle_status)
    pm_actions_layout.addWidget(btn_breakdown)
    pm_actions_layout.addWidget(btn_delete_project)
    right_layout.addLayout(pm_actions_layout)

    # --- AI ASSISTANT SECTION ---
    ai_label = QLabel("🤖 AI Insights & Reporting")
    ai_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 15px;")
    right_layout.addWidget(ai_label)

    btn_report = QPushButton("📝 Generate Daily Standup Report")
    btn_report.setStyleSheet("background-color: #007acc; color: white; font-weight: bold;")
    btn_report.clicked.connect(generate_daily_report)
    right_layout.addWidget(btn_report)

    ai_output_widget = QTextEdit()
    ai_output_widget.setReadOnly(True)
    ai_output_widget.setFixedHeight(120)
    ai_output_widget.setPlaceholderText("AI insights and daily reports will appear here...")
    right_layout.addWidget(ai_output_widget)

    # --- ASSEMBLE ---
    main_layout.addWidget(left_panel)
    main_layout.addWidget(divider)
    main_layout.addWidget(right_panel)

    return main_window

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(CONFIG["THEME_QSS"])
    
    window = build_ui()
    load_data() 
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()