"""Audit report archiving, retention cleanup, and archive metadata."""
from datetime import datetime, timedelta
from pathlib import Path
import tarfile
import tempfile
import os


def process_audit_files(config, logger) -> dict:
    workspace = Path(config["paths"]["workspace"])
    archive_dir = workspace / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Only raw *.audit files directly in the workspace are input. Archives are kept separately.
    source_files = sorted(p for p in workspace.glob("*.audit") if p.is_file())
    if not source_files:
        logger.info("No raw .audit files found.")
        return {"archived_count": 0, "archive_path": None}

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    final_path = archive_dir / f"audit_{stamp}.tar.gz"
    fd, temp_name = tempfile.mkstemp(prefix=".sysaudit_", suffix=".tar.gz", dir=str(archive_dir))
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        with tarfile.open(temp_path, "w:gz") as tar:
            for source in source_files:
                tar.add(source, arcname=source.name)

        # Verify the archive can be opened and contains the expected members before deleting inputs.
        with tarfile.open(temp_path, "r:gz") as tar:
            archived_names = set(tar.getnames())
        expected_names = {p.name for p in source_files}
        if not expected_names.issubset(archived_names):
            raise RuntimeError("Archive verification failed; original .audit files were kept.")

        os.replace(temp_path, final_path)

        deleted_count = 0
        for source in source_files:
            source.unlink()
            deleted_count += 1

        logger.info("Successfully created archive %s from %s raw audit file(s).", final_path.name, deleted_count)
        return {"archived_count": deleted_count, "archive_path": str(final_path)}
    except Exception:
        logger.exception("Archive operation failed; raw source files should be retained.")
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def prune_old_archives(config, logger) -> int:
    archive_dir = Path(config["paths"]["workspace"]) / "archives"
    if not archive_dir.exists():
        return 0
    retention_days = int(config["storage"]["archive_retention_days"])
    cutoff = datetime.now().timestamp() - retention_days * 24 * 60 * 60
    removed = 0
    for archive in archive_dir.iterdir():
        if archive.is_file() and (archive.name.endswith(".tar.gz") or archive.name.endswith(".zip")):
            try:
                if archive.stat().st_mtime < cutoff:
                    archive.unlink()
                    removed += 1
                    logger.info("Deleted expired archive %s.", archive.name)
            except OSError:
                logger.exception("Could not remove expired archive %s.", archive)
    logger.info("Archive pruning complete. Removed %s expired archive(s).", removed)
    return removed


def get_archive_summary(config, logger) -> dict:
    archive_dir = Path(config["paths"]["workspace"]) / "archives"
    archives = []
    if archive_dir.exists():
        for path in archive_dir.iterdir():
            if path.is_file() and (path.name.endswith(".tar.gz") or path.name.endswith(".zip")):
                try:
                    stat = path.stat()
                    archives.append((path, stat.st_size, stat.st_mtime))
                except OSError:
                    logger.warning("Could not read archive metadata for %s.", path)

    if not archives:
        summary = {
            "archive_count": 0, "largest_name": "None",
            "largest_size_bytes": 0, "largest_modified": "None"
        }
    else:
        largest = max(archives, key=lambda item: item[1])
        modified = datetime.fromtimestamp(largest[2]).astimezone().isoformat(timespec="seconds")
        summary = {
            "archive_count": len(archives),
            "largest_name": largest[0].name,
            "largest_size_bytes": largest[1],
            "largest_modified": modified
        }

    logger.info(
        "Archive summary: count=%s; largest=%s; size_bytes=%s; modified=%s",
        summary["archive_count"], summary["largest_name"],
        summary["largest_size_bytes"], summary["largest_modified"]
    )
    return summary
