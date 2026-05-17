@echo off
chcp 65001 >nul
title LLM Security Extension - 开发环境启动器

echo ============================================
echo  LLM Security Extension - 开发环境启动器
echo ============================================
echo.

:: 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: 检查 backend venv 是否存在
if not exist "backend\venv\Scripts\activate.bat" (
    echo [警告] Backend 虚拟环境不存在，正在创建...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    cd ..
    echo [完成] Backend 虚拟环境创建完成
    echo.
)

:: 检查 admin node_modules 是否存在
if not exist "admin\node_modules" (
    echo [警告] Admin 依赖不存在，正在安装...
    cd admin
    call npm install
    cd ..
    echo [完成] Admin 依赖安装完成
    echo.
)

:: 检查 extension node_modules 是否存在
if not exist "extension\node_modules" (
    echo [警告] Extension 依赖不存在，正在安装...
    cd extension
    call npm install
    cd ..
    echo [完成] Extension 依赖安装完成
    echo.
)

echo.
echo 正在启动所有服务...
echo.

:: 启动 Backend (FastAPI)
echo [启动] Backend FastAPI 服务 (端口: 8000)
start "Backend - FastAPI" cmd /k "cd /d "%SCRIPT_DIR%backend" && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 等待 2 秒让 backend 先启动
timeout /t 2 /nobreak >nul

:: 启动 Admin Panel
echo [启动] Admin 管理面板 (端口: 3000)
start "Admin Panel" cmd /k "cd /d "%SCRIPT_DIR%admin" && npm run dev"

:: 启动 Extension
echo [启动] Extension 开发服务 (端口: 5173)
start "Extension Dev" cmd /k "cd /d "%SCRIPT_DIR%extension" && npm run dev"

echo.
echo ============================================
echo  所有服务已启动！
echo ============================================
echo.
echo  服务地址:
echo    Backend API:  http://127.0.0.1:8000
echo    API 文档:     http://127.0.0.1:8000/docs
echo    Admin 面板:   http://localhost:3000
echo    Extension:    http://localhost:5173
echo.
echo  提示: 关闭此窗口不会影响已启动的服务
echo        如需停止所有服务，请关闭各自的终端窗口
echo ============================================
echo.

pause
