#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo: sudo bash install.sh"
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/opt/sysaudit"
CONFIG_DIR="/etc/sysaudit"
WORKSPACE="/course_project/audit"
STATE_DIR="/var/lib/sysaudit"

if ! id auditmanager >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$STATE_DIR" --shell /usr/sbin/nologin auditmanager
fi

install -d -o root -g root -m 755 "$APP_DIR" "$CONFIG_DIR"
install -d -o auditmanager -g auditmanager -m 750 "$WORKSPACE" "$WORKSPACE/archives" "$STATE_DIR"
touch /var/log/sysaudit_daemon.log
chown auditmanager:auditmanager /var/log/sysaudit_daemon.log
chmod 640 /var/log/sysaudit_daemon.log

# Copy source code, not local test data or virtual environments.
cp -R "$SOURCE_DIR/main.py" "$SOURCE_DIR/modules" "$SOURCE_DIR/tools" "$APP_DIR/"
chown -R root:root "$APP_DIR"
chmod 755 "$APP_DIR/main.py"

if [[ ! -f "$CONFIG_DIR/sysaudit.cfg" ]]; then
  install -o root -g root -m 644 "$SOURCE_DIR/sysaudit.cfg" "$CONFIG_DIR/sysaudit.cfg"
  # The service account must be able to read the config.
fi

install -o root -g root -m 644 "$SOURCE_DIR/systemd/sysaudit.service" /etc/systemd/system/sysaudit.service
systemctl daemon-reload
systemctl enable --now sysaudit.service

echo
echo "Installed. Check status with:"
echo "  sudo systemctl status sysaudit.service"
echo "View logs with:"
echo "  sudo tail -f /var/log/sysaudit_daemon.log"
echo
echo "To create a sample report:"
echo "  sudo -u auditmanager /usr/bin/python3 $APP_DIR/tools/generate_sample_audit.py --workspace $WORKSPACE"
echo "For an immediate one-time cycle:"
echo "  sudo -u auditmanager /usr/bin/python3 $APP_DIR/main.py --config $CONFIG_DIR/sysaudit.cfg --once"
