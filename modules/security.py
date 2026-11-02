"""Account authorization and explicit local-user delegation."""
import json
import os
import pwd
import tempfile
from pathlib import Path


class SecurityError(Exception):
    pass


def current_username() -> str:
    return pwd.getpwuid(os.getuid()).pw_name


def _read_delegates(config) -> list[str]:
    path = Path(config["paths"]["delegation_file"])
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise ValueError("delegation file must contain a JSON list of usernames")
        return sorted(set(data))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SecurityError(f"Cannot read delegation list: {exc}") from exc


def check_identity(config) -> None:
    user = current_username()
    primary = config["general"]["authorized_user"]
    delegated = _read_delegates(config)
    if user != primary and user not in delegated:
        raise SecurityError(
            f"account '{user}' is not authorized. Run as '{primary}' or ask that account to delegate access."
        )


def _require_primary(config):
    user = current_username()
    primary = config["general"]["authorized_user"]
    if user != primary:
        raise SecurityError(f"Only '{primary}' can manage delegated users; current account is '{user}'.")


def add_delegate(username: str, config) -> None:
    _require_primary(config)
    try:
        pwd.getpwnam(username)  # Confirm this is a local Linux account.
    except KeyError as exc:
        raise SecurityError(f"Local Linux account '{username}' does not exist.") from exc

    path = Path(config["paths"]["delegation_file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    users = _read_delegates(config)
    if username not in users:
        users.append(username)
    _atomic_write(path, users)


def remove_delegate(username: str, config) -> None:
    _require_primary(config)
    path = Path(config["paths"]["delegation_file"])
    users = [u for u in _read_delegates(config) if u != username]
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, users)


def list_delegates(config) -> list[str]:
    _require_primary(config)
    return _read_delegates(config)


def _atomic_write(path: Path, users: list[str]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix="delegates_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(sorted(set(users)), handle, indent=2)
            handle.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
