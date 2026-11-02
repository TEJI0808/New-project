# Suggested five-person responsibility split

- Member 1: `main.py`, `modules/config.py`, CLI, help, overrides, error codes, integration.
- Member 2: `modules/audit.py`, compression, retention, archive statistics.
- Member 3: `modules/security.py`, authorization and delegation.
- Member 4: `modules/logging_system.py`, `modules/monitoring.py`, logging and storage ceiling.
- Member 5: `systemd/sysaudit.service`, `install.sh`, `tests/`, deployment and testing.

All members should test their features, review integration, and contribute to the presentation. This is a suggested allocation, not proof of individual work.
