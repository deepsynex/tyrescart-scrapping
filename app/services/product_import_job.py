"""
app/services/product_import_job.py - Chunked, single-flight background runner for
the Product CSV importer.

Why this exists: a synchronous CSV import inside the Flask request handler used to
run for as long as the file took to process (minutes for a few thousand rows). That
routinely exceeded Cloudflare's upstream timeout, and Cloudflare returning an error
page to the browser did NOT stop the request on the server -- the worker kept running
and kept writing to the database long after the admin's browser gave up, corrupting
data with partially-applied imports racing against anything done afterwards.

This module fixes both problems:
  - The upload request only validates the file and hands it to a background thread,
    returning immediately.
  - The actual import is split into chunks of CHUNK_SIZE rows, each run as its own
    call into ProductImporter.import_csv (so any single failure only affects that
    chunk, and progress is visible between chunks).
  - A single process-wide lock means only one import can run at a time; a second
    upload while one is in flight is rejected outright rather than silently queued
    or run concurrently against the same tables.
"""

import csv
import io
import threading
import time
import traceback

from services.product_importer import ProductImporter

MAX_ROWS = 50000
CHUNK_SIZE = 5000

_lock = threading.Lock()
_state_lock = threading.Lock()

# Single shared job record -- there is only ever one import in flight at a time.
_job = {
    "status": "idle",  # idle | running | completed | failed
}


class ImportAlreadyRunningError(Exception):
    pass


class ImportTooLargeError(Exception):
    def __init__(self, row_count):
        self.row_count = row_count
        super().__init__(f"CSV has {row_count} rows, which exceeds the {MAX_ROWS} row limit.")


def get_status():
    with _state_lock:
        return dict(_job)


def _set_state(**kwargs):
    with _state_lock:
        _job.update(kwargs)


def start_import(file_content, user_id=1):
    """
    Validates and launches a chunked CSV import on a background thread.
    Raises ImportAlreadyRunningError if a prior import is still running, or
    ImportTooLargeError if the file exceeds MAX_ROWS.
    Returns a dict describing the accepted job (row/chunk counts).
    """
    if not _lock.acquire(blocking=False):
        raise ImportAlreadyRunningError("A product CSV import is already running.")

    try:
        if isinstance(file_content, bytes):
            text = file_content.decode("utf-8-sig", errors="replace")
        else:
            text = str(file_content)

        stream = io.StringIO(text)
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
        total_rows = len(rows)

        if total_rows == 0:
            _lock.release()
            raise ValueError("CSV is empty.")

        if total_rows > MAX_ROWS:
            _lock.release()
            raise ImportTooLargeError(total_rows)

        chunks = [rows[i:i + CHUNK_SIZE] for i in range(0, total_rows, CHUNK_SIZE)]
        total_chunks = len(chunks)

        _set_state(
            status="running",
            total_rows=total_rows,
            total_chunks=total_chunks,
            current_chunk=0,
            processed_rows=0,
            imported=0,
            updated=0,
            errors=[],
            extra_attributes=[],
            matched_attributes=[],
            missing_attributes=[],
            started_at=time.time(),
            finished_at=None,
            message=f"Starting import of {total_rows} rows in {total_chunks} chunk(s)...",
        )

        thread = threading.Thread(
            target=_run_job,
            args=(fieldnames, chunks, user_id),
            daemon=True,
        )
        thread.start()

        return {
            "total_rows": total_rows,
            "total_chunks": total_chunks,
            "chunk_size": CHUNK_SIZE,
        }
    except (ValueError, ImportTooLargeError):
        raise
    except Exception:
        _lock.release()
        raise


def _run_job(fieldnames, chunks, user_id):
    try:
        total_imported = 0
        total_updated = 0
        all_errors = []
        matched_attributes = []
        extra_attributes = []
        missing_attributes = []
        processed_rows = 0
        total_chunks = len(chunks)

        for idx, chunk_rows in enumerate(chunks, start=1):
            _set_state(
                current_chunk=idx,
                message=f"Importing chunk {idx} of {total_chunks} ({len(chunk_rows)} rows)...",
            )

            chunk_base = processed_rows

            def _on_row_progress(rows_done_in_chunk, _chunk_total, _base=chunk_base):
                _set_state(processed_rows=_base + rows_done_in_chunk)

            chunk_csv = _rows_to_csv(fieldnames, chunk_rows)
            result = ProductImporter.import_csv(chunk_csv, user_id=user_id, progress_callback=_on_row_progress)

            if not result.get("success"):
                all_errors.append(f"Chunk {idx}: {result.get('error', 'Import failed')}")
            else:
                total_imported += result.get("imported", 0)
                total_updated += result.get("updated", 0)
                all_errors.extend(result.get("errors") or [])
                for a in (result.get("matched_attributes") or []):
                    if a not in matched_attributes:
                        matched_attributes.append(a)
                for a in (result.get("extra_attributes") or []):
                    if a not in extra_attributes:
                        extra_attributes.append(a)
                for a in (result.get("missing_attributes") or []):
                    if a not in missing_attributes:
                        missing_attributes.append(a)

            processed_rows += len(chunk_rows)
            _set_state(
                processed_rows=processed_rows,
                imported=total_imported,
                updated=total_updated,
                errors=all_errors,
                matched_attributes=matched_attributes,
                extra_attributes=extra_attributes,
                missing_attributes=missing_attributes,
            )

        _set_state(
            status="completed",
            finished_at=time.time(),
            message=(
                f"Successfully processed {processed_rows} products "
                f"({total_imported} imported, {total_updated} updated)."
                + (f" {len(all_errors)} row error(s) logged." if all_errors else "")
            ),
        )
    except Exception as e:
        _set_state(
            status="failed",
            finished_at=time.time(),
            message=f"Import failed: {e}",
            errors=(get_status().get("errors") or []) + [traceback.format_exc()],
        )
    finally:
        _lock.release()


def _rows_to_csv(fieldnames, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
