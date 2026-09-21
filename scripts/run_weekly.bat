@echo off
REM ============================================================
REM  PromptForge 每周技术文章任务 - Windows 一键执行
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0.."

set "LOG_DIR=output\weekly_tech\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%I"
if "%TODAY%"=="" set "TODAY=unknown"
set "LOG_FILE=%LOG_DIR%\run_%TODAY%.log"

forfiles /p "%LOG_DIR%" /m run_*.log /d -60 /c "cmd /c del @path" 2>nul

echo [%date% %time%] === 每周技术文章任务开始 === >> "%LOG_FILE%"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [%date% %time%] 已激活 venv >> "%LOG_FILE%"
)

REM 默认：深度技术型 + newspaper + 推公众号
REM 想换风格：--style 专业分析型 / 通俗科普型 / 行业观察型 / 趋势预测型
python scripts\weekly_tech_task.py --style 深度技术型 --theme newspaper >> "%LOG_FILE%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] === 任务结束，退出码 %EXIT_CODE% === >> "%LOG_FILE%"

if not "%EXIT_CODE%"=="0" (
    echo ⚠️ 每周技术文章任务失败，退出码 %EXIT_CODE%
    echo ⚠️ 日志：%LOG_FILE%
)

endlocal & exit /b %EXIT_CODE%