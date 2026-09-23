@echo off
REM ============================================================
REM  PromptForge GitHub 日报 - Windows 一键执行
REM  用法：直接双击，或从计划任务调用
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0.."

REM ---- 日志目录 ----
set "LOG_DIR=output\github_repo_daily\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 用 PowerShell 取 yyyyMMdd
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%I"
if "%TODAY%"=="" set "TODAY=unknown"
set "LOG_FILE=%LOG_DIR%\run_%TODAY%.log"

REM 日志轮转：保留最近 30 天
forfiles /p "%LOG_DIR%" /m run_*.log /d -30 /c "cmd /c del @path" 2>nul

echo [%date% %time%] === GitHub 日报任务开始 === >> "%LOG_FILE%"

REM ---- 激活虚拟环境 ----
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [%date% %time%] 已激活 venv >> "%LOG_FILE%"
)

REM ---- 执行 GitHub 日报 ----
REM 默认：随机仓库 + 3 张配图 + newspaper 排版 + 推草稿箱
REM 想关掉推送：在末尾加 --no-publish
REM 想关掉配图：在末尾加 --illustration-count 0
python scripts\github_daily_task.py >> "%LOG_FILE%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] === 任务结束，退出码 %EXIT_CODE% === >> "%LOG_FILE%"

if not "%EXIT_CODE%"=="0" (
    echo ⚠️ GitHub 日报任务失败，退出码 %EXIT_CODE%
    echo ⚠️ 日志：%LOG_FILE%
)

endlocal & exit /b %EXIT_CODE%