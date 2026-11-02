"""Workspace storage monitoring."""
from pathlib import Path


def directory_size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except (OSError, PermissionError):
            # A file disappearing during a scan should not crash the whole measurement.
            continue
    return total


def check_storage(config, logger):
    workspace = Path(config["paths"]["workspace"])
    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(f"Workspace does not exist or is not a directory: {workspace}")

    size_bytes = directory_size_bytes(workspace)
    limit_bytes = float(config["storage"]["max_storage_mb"]) * 1024 * 1024
    over_limit = size_bytes > limit_bytes
    logger.info(
        "Workspace storage check: %s bytes used; limit %.2f MB; over_limit=%s",
        size_bytes, config["storage"]["max_storage_mb"], over_limit
    )
    return size_bytes, over_limit
