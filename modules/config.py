"""Configuration loading and command-line overrides."""
from configparser import ConfigParser, Error as IniError
from pathlib import Path


class ConfigError(Exception):
    pass


def load_config(path: str) -> dict:
    cfg_path = Path(path).expanduser()
    if not cfg_path.is_file():
        raise FileNotFoundError(cfg_path)

    parser = ConfigParser()
    try:
        with cfg_path.open("r", encoding="utf-8") as handle:
            parser.read_file(handle)
    except (OSError, IniError) as exc:
        raise ConfigError(str(exc)) from exc

    required_sections = ("GENERAL", "PATHS", "STORAGE", "SCHEDULE")
    missing = [section for section in required_sections if not parser.has_section(section)]
    if missing:
        raise ConfigError("Missing section(s): " + ", ".join(missing))

    try:
        data = {
            "general": {
                "authorized_user": parser.get("GENERAL", "authorized_user"),
            },
            "paths": {
                "workspace": parser.get("PATHS", "workspace"),
                "log_file": parser.get("PATHS", "log_file"),
                "state_file": parser.get("PATHS", "state_file", fallback="/var/lib/sysaudit/last_run.txt"),
                "delegation_file": parser.get("PATHS", "delegation_file", fallback="/var/lib/sysaudit/delegated_users.json"),
            },
            "storage": {
                "max_storage_mb": parser.getfloat("STORAGE", "max_storage_mb"),
                "archive_retention_days": parser.getint("STORAGE", "archive_retention_days"),
                "stop_on_limit": parser.getboolean("STORAGE", "stop_on_limit", fallback="false"),
            },
            "schedule": {
                "interval_days": parser.getint("SCHEDULE", "interval_days"),
            },
        }
    except (ValueError, IniError) as exc:
        raise ConfigError(f"Invalid or missing setting: {exc}") from exc

    if data["storage"]["max_storage_mb"] <= 0:
        raise ConfigError("max_storage_mb must be greater than zero.")
    if data["storage"]["archive_retention_days"] < 1:
        raise ConfigError("archive_retention_days must be at least 1.")
    if data["schedule"]["interval_days"] < 1:
        raise ConfigError("interval_days must be at least 1.")
    for key, value in data["paths"].items():
        if not value:
            raise ConfigError(f"Path setting '{key}' cannot be empty.")
    return data


def apply_cli_overrides(config: dict, args) -> dict:
    """Return a separate effective config; never writes changes back to the INI file."""
    result = {section: dict(values) for section, values in config.items()}
    if args.workspace:
        result["paths"]["workspace"] = args.workspace
    if args.log_file:
        result["paths"]["log_file"] = args.log_file
    if args.max_storage_mb is not None:
        if args.max_storage_mb <= 0:
            raise ConfigError("--max-storage-mb must be greater than zero.")
        result["storage"]["max_storage_mb"] = args.max_storage_mb
    if args.retention_days is not None:
        if args.retention_days < 1:
            raise ConfigError("--retention-days must be at least 1.")
        result["storage"]["archive_retention_days"] = args.retention_days
    if args.interval_days is not None:
        if args.interval_days < 1:
            raise ConfigError("--interval-days must be at least 1.")
        result["schedule"]["interval_days"] = args.interval_days
    return result
