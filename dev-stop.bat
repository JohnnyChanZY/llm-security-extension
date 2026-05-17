@echo off
chcp 65001 >nul
title LLM Security Extension - 停止所有服务

echo ============================================
echo  LLM Security Extension - 停止所有服务
echo ============================================
echo.

echo 正在停止所有 Node.js 服务...
taskkill /F /IM node.exe 2>nul
if %errorlevel%==0 (
    echo [完成] Node.js 服务已停止
) else (
    echo [信息] 没有运行中的 Node.js 服务
)

echo 正在停止所有 Python 服务...
taskkill /F /IM python.exe 2>nul
if %errorlevel%==0 (
    echo [完成] Python 服务已停止
) else (
    echo [信息] 没有运行中的 Python 服务
)

echo.
echo ============================================
echo  所有服务已停止
echo ============================================
echo.

pause
