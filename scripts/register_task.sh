#!/usr/bin/env bash
# ============================================================
#  注册 systemd timer：每天 08:00 执行 run_daily.sh
#  对应 Windows 的 register_task.ps1
#  用法：./scripts/register_task.sh [HH:MM]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RUN_SH="$PROJECT_ROOT/scripts/run_daily.sh"
TASK_TIME="${1:-08:00}"
SERVICE_NAME="promptforge-daily"
UNIT_DIR="$HOME/.config/systemd/user"

if [ ! -f "$RUN_SH" ]; then
    echo "❌ 找不到 $RUN_SH" >&2
    exit 1
fi
chmod +x "$RUN_SH"

mkdir -p "$UNIT_DIR"

cat > "$UNIT_DIR/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=PromptForge 每日生图 + 鉴赏 + 排版
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_ROOT
ExecStart=$RUN_SH
Restart=on-failure
RestartSec=5min
TimeoutStartSec=1h
StandardOutput=journal
StandardError=journal
EOF

cat > "$UNIT_DIR/${SERVICE_NAME}.timer" <<EOF
[Unit]
Description=每天 $TASK_TIME 触发 PromptForge 每日任务

[Timer]
OnCalendar=*-*-* $TASK_TIME:00
Persistent=true
RandomizedDelaySec=5min
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}.timer"

echo "✅ 已注册：${SERVICE_NAME}.timer"
echo "   项目目录：$PROJECT_ROOT"
echo "   执行时间：每天 $TASK_TIME"
echo ""
echo "验证："
echo "   systemctl --user list-timers ${SERVICE_NAME}.timer"
echo "   systemctl --user start ${SERVICE_NAME}.service    # 立即测试"
echo "   journalctl --user -u ${SERVICE_NAME}.service -n 100 --no-pager"
echo ""
echo "⚠️  服务器建议执行一次（未登录也跑）："
echo "   sudo loginctl enable-linger $USER"