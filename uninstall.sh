#!/usr/bin/env bash
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo: sudo bash uninstall.sh"
  exit 1
fi
systemctl disable --now sysaudit.service 2>/dev/null || true
rm -f /etc/systemd/system/sysaudit.service
systemctl daemon-reload
echo "Service removed. Application files, configuration, logs, audit reports, and auditmanager account were kept."
echo "Remove those manually only if you are sure you no longer need them."
