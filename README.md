# CIS 341 – System Health Monitor & Security Auditing Daemon

A Python implementation of the group-project requirements. It is designed for Ubuntu/Linux. The systemd service requires a Linux environment with systemd; ordinary Python functions and tests can also be run in WSL.

## What is included

- `main.py`: CLI, config integration, exit codes, one-time and daemon modes.
- `modules/config.py`: INI configuration and CLI overrides.
- `modules/security.py`: `auditmanager` identity check and explicit delegated-user list.
- `modules/audit.py`: discovers root-level `*.audit` files, creates verified `.tar.gz` archives, removes source files only after successful verification, prunes old archives, and reports archive metadata.
- `modules/monitoring.py`: measures the total workspace tree size and checks the configured ceiling.
- `modules/logging_system.py`: timestamped INFO/WARNING/ERROR logging.
- `tools/generate_sample_audit.py`: creates harmless demonstration `.audit` reports. This is not a complete security scanner.
- `tests/`: automated unit tests.
- `systemd/sysaudit.service`: background daemon service.
- `install.sh`: installs the service on Ubuntu/Linux.

## Requirements

- Python 3.10 or newer
- Ubuntu/Linux
- No third-party Python packages are required.
- For service installation: systemd and sudo/root access.

## A. Quick test as your current Linux user

This tests the processing modules without installing a system service or changing Linux accounts.

1. Open Ubuntu/WSL terminal.
2. Move into the extracted project folder:
   ```bash
   cd ~/CIS341_System_Audit_Project
   ```
   Use the actual folder path where you extracted the ZIP.
3. Check Python:
   ```bash
   python3 --version
   ```
4. Generate a sample report:
   ```bash
   python3 tools/generate_sample_audit.py --workspace ./demo_audit
   ```
5. Run the unit tests:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
6. Run the main program's help:
   ```bash
   python3 main.py
   ```
   Help is also shown by:
   ```bash
   python3 main.py --help
   ```

The normal config requires the account `auditmanager`, so for a quick test as your own user, make a local demo config:

```bash
cp sysaudit.cfg demo.cfg
```

Edit `demo.cfg` and change these values:
- `authorized_user` to the Linux username shown by `whoami`
- `workspace` to the full path of this project's `demo_audit` folder
- `log_file` to a path in your home directory, such as `/home/YOUR_USERNAME/sysaudit-demo.log`
- `state_file` and `delegation_file` to paths in your home directory

Then run one cycle:
```bash
python3 main.py --config demo.cfg --once
```

Check the results:
```bash
find demo_audit -maxdepth 2 -type f -print
cat ~/sysaudit-demo.log
```
Replace `YOUR_USERNAME` with the result of `whoami`. The `.audit` input should have moved into `demo_audit/archives/` inside a `.tar.gz` file.

## B. Install and run as the required `auditmanager` account

Do this only in an Ubuntu/Linux environment where you have sudo access. The installer creates the system account, runtime folders, and systemd service.

1. Extract the ZIP into your Ubuntu home folder.
2. Enter the project directory:
   ```bash
   cd ~/CIS341_System_Audit_Project
   ```
3. Run the installer:
   ```bash
   sudo bash install.sh
   ```
4. Check the service:
   ```bash
   sudo systemctl status sysaudit.service
   ```
5. View the daemon log:
   ```bash
   sudo tail -f /var/log/sysaudit_daemon.log
   ```
6. Create a demonstration audit report:
   ```bash
   sudo -u auditmanager python3 /opt/sysaudit/tools/generate_sample_audit.py --workspace /course_project/audit
   ```
7. Run one immediate processing cycle:
   ```bash
   sudo -u auditmanager python3 /opt/sysaudit/main.py --config /etc/sysaudit/sysaudit.cfg --once
   ```
8. Confirm the archive:
   ```bash
   sudo find /course_project/audit -maxdepth 2 -type f -ls
   ```
9. Restart or stop the background service:
   ```bash
   sudo systemctl restart sysaudit.service
   sudo systemctl stop sysaudit.service
   sudo systemctl start sysaudit.service
   ```

The daemon service starts at boot. Its first scheduled cycle is at the next local midnight; later cycles are scheduled every three days. Use `--once` for an immediate demonstration run.

## C. Delegating access to another local account

Only `auditmanager` can add or remove delegated accounts. First make sure the other account already exists.

Register a delegate:
```bash
sudo -u auditmanager python3 /opt/sysaudit/main.py --config /etc/sysaudit/sysaudit.cfg --delegate-user alice
```

List delegates:
```bash
sudo -u auditmanager python3 /opt/sysaudit/main.py --config /etc/sysaudit/sysaudit.cfg --list-delegates
```

Remove a delegate:
```bash
sudo -u auditmanager python3 /opt/sysaudit/main.py --config /etc/sysaudit/sysaudit.cfg --revoke-delegate alice
```

A delegated account can run the program only if it also has the required read/write access to the configured workspace, state file, and log file. The delegation list grants program authorization; it does not automatically change Linux file permissions. Keep permissions limited and configure group access separately if your instructor expects file-group delegation.

## D. Configuration

The installed configuration is `/etc/sysaudit/sysaudit.cfg`.

- `authorized_user`: primary authorized Linux account.
- `workspace`: folder containing raw `.audit` reports; archives are stored in its `archives/` subfolder.
- `log_file`: application log.
- `state_file`: remembers the last successful scheduled run.
- `delegation_file`: delegated-account list.
- `max_storage_mb`: storage ceiling in MB.
- `archive_retention_days`: archive age limit; default is 14 days.
- `stop_on_limit`: `false` means warn and continue; `true` means stop with exit code 5.
- `interval_days`: daemon interval; default is 3 days.

CLI overrides apply only to that run and do not edit the config file. Example:
```bash
sudo -u auditmanager python3 /opt/sysaudit/main.py --config /etc/sysaudit/sysaudit.cfg --once --max-storage-mb 150
```

## E. Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | General/unexpected error |
| 2 | Identity violation |
| 3 | Missing or invalid configuration |
| 4 | Invalid workspace |
| 5 | Storage ceiling reached when `stop_on_limit = true` |

## F. Important design notes / limitations to discuss as a team

1. The assignment says raw `.audit` files are generated by a scanner. It does not clearly say that the group must build a scanner. The included generator is for demonstration/test data only. Confirm with your instructor whether a scanner is provided or expected.
2. The daemon waits until the next local midnight for its first scheduled cycle, then runs every configured number of days. If the daemon was down when a scheduled cycle was due, it catches up when restarted.
3. This starter uses a simple JSON allowlist for delegated users. It grants program-level authorization only; it does not grant OS file permissions. Explain this distinction in the presentation.
4. `install.sh` uses a system service account named `auditmanager`. It does not set a password or allow interactive login.
5. Run and test the project in your course-approved Linux environment. WSL versions may differ in systemd support; if systemd is unavailable, use the manual `--once` mode for code testing and a Linux VM for service deployment evidence.
6. The code is a course-project implementation, not a production security product. Review it with your group and instructor, test on disposable sample data, and do not point it at important files.

## G. Suggested presentation demo

1. Show the help screen.
2. Generate a sample `.audit` file.
3. Show the raw file before processing.
4. Run `--once` and show the compressed archive.
5. Show that the raw input was removed only after the archive was verified.
6. Show the log and archive metadata.
7. Show storage warning behavior by temporarily setting a low threshold in a test config.
8. Show unauthorized-user rejection and delegated-user registration in a controlled Linux test.
9. Show systemd service status and the schedule configuration.
