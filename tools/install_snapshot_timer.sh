#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

mkdir -p "$USER_SYSTEMD_DIR"

cat > "$USER_SYSTEMD_DIR/fpl-snapshot-collector.service" <<EOF
[Unit]
Description=FPL pre-deadline snapshot collector

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m tools.collect_predeadline_snapshot
EOF

cat > "$USER_SYSTEMD_DIR/fpl-snapshot-collector.timer" <<EOF
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

systemctl --user daemon-reload
systemctl --user enable --now fpl-snapshot-collector.timer
systemctl --user start fpl-snapshot-collector.service

echo
echo "FPL snapshot timer installed and started."
echo "Status:"
systemctl --user --no-pager status fpl-snapshot-collector.timer || true
