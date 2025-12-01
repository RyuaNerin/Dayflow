<div align="center">

# ⏱️ Dayflow for Windows

**Intelligent Time Tracking & Productivity Analysis Tool**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)

*Silent Background Recording → AI Analysis → Visual Timeline*

[中文](README.md) | **English**

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎥 **Low-Power Recording** | 1 FPS ultra-low resource usage, runs silently in background |
| 🤖 **AI-Powered Analysis** | Vision LLM identifies screen activities and auto-categorizes |
| 📊 **Timeline Visualization** | Intuitive daily time allocation view at a glance |
| 💡 **Productivity Insights** | AI-driven efficiency assessment and improvement suggestions |
| 🔒 **Privacy First** | Local data storage, auto-cleanup after analysis |

---

## 🚀 Quick Start

### Requirements

- Windows 10/11 (64-bit)
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (added to system PATH)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/Dayflow.git
cd Dayflow

# 2. Create Conda environment (recommended)
conda create -n dayflow python=3.11 -y
conda activate dayflow

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the app
python main.py
```

---

## 📖 User Guide

### 1️⃣ Configure API Key

1. Open the app, click **⚙️ Settings** on the left sidebar
2. Enter your API Key
3. Click **Test Connection** to verify
4. Click **Save**

> 💡 API Endpoint: `https://apis.iflow.cn/v1`

### 2️⃣ Start Recording

1. Click **▶ Start Recording**
2. The app records your screen at 1 FPS in the background
3. Video chunks are saved every 60 seconds
4. Automatically sent to cloud AI for analysis

### 3️⃣ View Timeline

- Analysis results appear on the home timeline
- Each card represents an activity period
- Includes: category, applications used, productivity score

### 4️⃣ System Tray

- Close window → Minimizes to tray, keeps running
- Double-click tray icon → Open main window
- Right-click tray → Control recording / Exit

---

## 📁 Project Structure

```
Dayflow/
├── 📄 main.py              # Entry point
├── ⚙️ config.py            # Configuration
├── 📦 requirements.txt     # Dependencies
│
├── 🧠 core/                # Core logic
│   ├── types.py            # Data models
│   ├── recorder.py         # Screen capture (dxcam)
│   ├── llm_provider.py     # AI API integration
│   └── analysis.py         # Analysis scheduler
│
├── 💾 database/            # Data layer
│   ├── schema.sql          # Table definitions
│   └── storage.py          # SQLite management
│
└── 🎨 ui/                  # UI layer
    ├── main_window.py      # Main window
    └── timeline_view.py    # Timeline component
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DAYFLOW_API_URL` | API endpoint | `https://apis.iflow.cn/v1` |
| `DAYFLOW_API_KEY` | API key | (empty) |
| `DAYFLOW_API_MODEL` | AI model | `qwen3-vl-plus` |

### Data Directory

```
%LOCALAPPDATA%\Dayflow\
├── dayflow.db      # Database
├── chunks/         # Video chunks (auto-deleted after analysis)
└── dayflow.log     # Runtime logs
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| GUI Framework | PySide6 (Qt6) |
| Screen Capture | dxcam (DirectX) |
| Video Processing | OpenCV |
| HTTP Client | httpx (HTTP/2) |
| Database | SQLite |
| AI Analysis | OpenAI-compatible API |

---

## 📄 License

[MIT License](LICENSE) © 2024

---

<div align="center">

**If you find this useful, please give it a ⭐ Star!**

</div>
