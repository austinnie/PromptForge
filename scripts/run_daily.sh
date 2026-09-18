#!/usr/bin/env bash
# ============================================================
#  PromptForge 每日任务 - Linux 执行脚本（对应 run_daily.bat）
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

LOG_DIR="output/daily/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d).log"

# 日志轮转：保留 30 天
find "$LOG_DIR" -name 'run_*.log' -type f -mtime +30 -delete 2>/dev/null || true

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== PromptForge 每日任务开始 ==="

# 激活虚拟环境
for venv in venv .venv; do
    if [ -f "$venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$venv/bin/activate"
        log "已激活 $venv: $(which python)"
        break
    fi
done

python scripts/daily_task.py --count 6 --theme newspaper --vary-preset >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

log "=== 任务结束，退出码 $EXIT_CODE ==="

if [ "$EXIT_CODE" -ne 0 ]; then
    log "⚠️ 任务失败，日志：$LOG_FILE"
fi

exit $EXIT_CODE