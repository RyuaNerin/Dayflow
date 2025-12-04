@echo off
chcp 65001 >nul
echo ========================================
echo   Dayflow 一键发布工具
echo ========================================
echo.

REM 检查 GITHUB_TOKEN
if "%GITHUB_TOKEN%"=="" (
    echo [警告] 未设置 GITHUB_TOKEN 环境变量
    echo.
    echo 请先设置 Token:
    echo   set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    echo.
    echo 获取 Token: https://github.com/settings/tokens
    echo 需要勾选 "repo" 权限
    echo.
    pause
    exit /b 1
)

REM 激活 conda 环境并运行
call C:\Users\L\anaconda3\Scripts\activate.bat dayflow
python release.py %*

pause
