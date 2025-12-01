<div align="center">

# ⏱️ Dayflow for Windows

**智能时间追踪与生产力分析工具**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)

*后台静默录屏 → AI 智能分析 → 可视化时间轴*

**中文** | [English](README_EN.md)

</div>

---

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 🎥 **低功耗录屏** | 1 FPS 极低资源占用，后台静默运行 |
| 🤖 **AI 智能分析** | 视觉大模型识别屏幕活动，自动归类 |
| 📊 **时间轴可视化** | 直观展示每日时间分配，一目了然 |
| 💡 **生产力洞察** | AI 驱动的效率评估与改进建议 |
| 🔒 **隐私安全** | 数据本地存储，分析后自动清理视频 |

---

## 🚀 快速开始

### 环境要求

- Windows 10/11 (64-bit)
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (添加到系统 PATH)

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/Dayflow.git
cd Dayflow

# 2. 创建 Conda 环境（推荐）
conda create -n dayflow python=3.11 -y
conda activate dayflow

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动应用
python main.py
```

---

## 📖 使用指南

### 1️⃣ 配置 API Key

1. 打开应用，点击左侧 **⚙️ 设置**
2. 输入你的心流 API Key
3. 点击 **测试连接** 验证
4. 点击 **保存**

> 💡 API 地址：`https://apis.iflow.cn/v1`

### 2️⃣ 开始录制

1. 点击 **▶ 开始录制**
2. 程序在后台以 1 FPS 静默录屏
3. 每 60 秒生成一个视频切片
4. 自动发送到云端 AI 分析

### 3️⃣ 查看时间轴

- 分析结果自动显示在首页时间轴
- 每张卡片代表一段活动时间
- 包含：活动类别、应用程序、生产力评分

### 4️⃣ 系统托盘

- 关闭窗口 → 最小化到托盘继续运行
- 双击托盘图标 → 打开主窗口
- 右键托盘 → 控制录制/退出

---

## 📁 项目结构

```
Dayflow/
├── 📄 main.py              # 启动入口
├── ⚙️ config.py            # 配置文件
├── 📦 requirements.txt     # 依赖清单
│
├── 🧠 core/                # 核心逻辑
│   ├── types.py            # 数据模型
│   ├── recorder.py         # 屏幕录制 (dxcam)
│   ├── llm_provider.py     # AI API 交互
│   └── analysis.py         # 分析调度器
│
├── 💾 database/            # 数据层
│   ├── schema.sql          # 表结构定义
│   └── storage.py          # SQLite 管理
│
└── 🎨 ui/                  # 界面层
    ├── main_window.py      # 主窗口
    └── timeline_view.py    # 时间轴组件
```

---

## ⚙️ 配置选项

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DAYFLOW_API_URL` | API 地址 | `https://apis.iflow.cn/v1` |
| `DAYFLOW_API_KEY` | API 密钥 | (空) |
| `DAYFLOW_API_MODEL` | AI 模型 | `qwen3-vl-plus` |

### 数据目录

```
%LOCALAPPDATA%\Dayflow\
├── dayflow.db      # 数据库
├── chunks/         # 视频切片（分析后自动删除）
└── dayflow.log     # 运行日志
```

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 (Qt6) |
| 屏幕捕获 | dxcam (DirectX) |
| 视频处理 | OpenCV |
| 网络请求 | httpx (HTTP/2) |
| 数据存储 | SQLite |
| AI 分析 | 心流 API (OpenAI 兼容) |

---

## 📄 许可证

[MIT License](LICENSE) © 2024

---

<div align="center">

**如果觉得有用，请给个 ⭐ Star！**

</div>
