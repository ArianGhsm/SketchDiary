from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from config import DATA_DIR, DB_PATH


def build_database_backup_zip() -> tuple[bytes, str]:
    source_path = Path(DB_PATH)
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"sketchdiary_db_backup_{timestamp}.zip"
    temp_db_path: Path | None = None
    source_conn = sqlite3.connect(source_path)
    backup_conn = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="db_backup_",
            suffix=".db",
            dir=DATA_DIR,
            delete=False,
        ) as tmp_file:
            temp_db_path = Path(tmp_file.name)

        backup_conn = sqlite3.connect(temp_db_path)
        with backup_conn:
            source_conn.backup(backup_conn)
    finally:
        source_conn.close()
        if backup_conn is not None:
            backup_conn.close()

    try:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_db_path, arcname=source_path.name)
        return buffer.getvalue(), archive_name
    finally:
        if temp_db_path and temp_db_path.exists():
            temp_db_path.unlink()
