@echo off
chcp 65001 >nul
title Dayflow 打包工具

echo ========================================
echo   Dayflow 打包工具
echo   正在检查环境...
echo ========================================
echo.

:: 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装 PyInstaller...
    pip install pyinstaller
)

:: 运行打包脚本
conda run -n dayflow --no-capture-output python build.py

echo.
pause
