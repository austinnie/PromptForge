@echo off
REM ============================================================
REM  PromptForge 每日任务 - Windows 一键执行
REM  用法：直接双击，或从计划任务调用
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

REM [改] %~dp0 已带尾部反斜杠，直接用 .. 更干净
cd /d "%~dp0.."

REM ---- 日志目录 ----
set "LOG_DIR=output\daily\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM [改] 用 PowerShell 取 yyyyMMdd，避免 %date% 依赖区域设置
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%I"
if "%TODAY%"=="" set "TODAY=unknown"
set "LOG_FILE=%LOG_DIR%\run_%TODAY%.log"

REM [改] 日志轮转：保留最近 30 天
forfiles /p "%LOG_DIR%" /m run_*.log /d -30 /c "cmd /c del @path" 2>nul

echo [%date% %time%] === PromptForge 每日任务开始 === >> "%LOG_FILE%"

REM ---- 激活虚拟环境（如果存在） ----
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [%date% %time%] 已激活 venv >> "%LOG_FILE%"
)

REM ---- 执行每日任务 ----
REM 默认：随机主题/预设 + 6 张图 + 每张不同构图 + 每张换同分类预设 + newspaper 排版 + 推草稿箱
REM 想关掉推送就在末尾加 --no-publish
python scripts\daily_task.py --count 6 --theme newspaper --vary-preset >> "%LOG_FILE%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] === 任务结束，退出码 %EXIT_CODE% === >> "%LOG_FILE%"

REM [改] 加引号，避免 EXIT_CODE 为空时变成 if not ==0 语法错误
if not "%EXIT_CODE%"=="0" (
    echo ⚠️ PromptForge 每日任务失败，退出码 %EXIT_CODE%
    echo ⚠️ 日志：%LOG_FILE%

    REM [可选] 失败时通知 webhook，启用前把 URL 换成你自己的
    REM curl -s -X POST "https://your-webhook.example.com/pf" ^
    REM      -H "Content-Type: application/json" ^
    REM      -d "{\"text\":\"PromptForge 每日任务失败 %TODAY%，退出码 %EXIT_CODE%\"}" >nul 2>&1
)

endlocal & exit /b %EXIT_CODE%