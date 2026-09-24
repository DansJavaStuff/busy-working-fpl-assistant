#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUN_USER="$(id -un)"
SERVICE_FILE="/etc/systemd/system/fpl-snapshot-collector.service"
TIMER_FILE="/etc/systemd/system/fpl-snapshot-collector.timer"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=FPL pre-deadline snapshot collector
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m tools.collect_predeadline_snapshot
EOF

sudo tee "$TIMER_FILE" > /dev/null <<EOF
[Unit]
Description=Check for FPL pre-deadline snapshot checkpoints

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
Persistent=true
Unit=fpl-snapshot-collector.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now fpl-snapshot-collector.timer

# Run once immediately. If the deadline is more than
# an hour away, this creates the baseline snapshot now.
sudo systemctl start fpl-snapshot-collector.service

echo
echo "FPL snapshot timer installed and started."
echo "Timer status:"
sudo systemctl --no-pager status fpl-snapshot-collector.timer || true
