#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUN_USER="$(id -un)"

SERVICE_FILE="/etc/systemd/system/fpl-chip-cache-warmer.service"
TIMER_FILE="/etc/systemd/system/fpl-chip-cache-warmer.timer"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Warm FPL chip opportunity cache
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$RUN_USER
Nice=10
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m tools.warm_chip_opportunity_cache
EOF

sudo tee "$TIMER_FILE" > /dev/null <<EOF
[Unit]
Description=Keep FPL chip opportunity cache warm

[Timer]
OnBootSec=3min
OnUnitActiveSec=20min
Persistent=true
Unit=fpl-chip-cache-warmer.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now fpl-chip-cache-warmer.timer

echo
echo "FPL chip cache warmer installed."
echo "It checks every 20 minutes at low CPU priority."
echo
sudo systemctl --no-pager status fpl-chip-cache-warmer.timer || true
