"""批量生成任务状态管理。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from generator.batch_processor import generate_batch_zip
from generator.stl_generator import ModelGenerationError

_lock = threading.Lock()
_jobs: dict[str, BatchJob] = {}


@dataclass
class BatchJob:
    job_id: str
    status: str = "pending"  # pending | running | done | error
    current: int = 0
    total: int = 0
    message: str = "等待开始…"
    zip_bytes: bytes | None = None
    zip_name: str | None = None
    error: str | None = None


def create_batch_job(file_bytes: bytes, style_id: str | None = None) -> str:
    """创建并后台启动批量生成任务，返回 job_id。"""
    job_id = uuid.uuid4().hex
    job = BatchJob(job_id=job_id)

    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_batch_job,
        args=(job_id, file_bytes, style_id),
        daemon=True,
    )
    thread.start()
    return job_id


def get_batch_job(job_id: str) -> BatchJob | None:
    with _lock:
        return _jobs.get(job_id)


def remove_batch_job(job_id: str) -> None:
    with _lock:
        _jobs.pop(job_id, None)


def _run_batch_job(job_id: str, file_bytes: bytes, style_id: str | None = None) -> None:
    job = get_batch_job(job_id)
    if job is None:
        return

    job.status = "running"
    job.message = "正在解析 Excel…"

    def on_progress(current: int, total: int, message: str) -> None:
        job.current = current
        job.total = total
        job.message = message

    try:
        zip_bytes, zip_name = generate_batch_zip(
            file_bytes, progress_callback=on_progress, style_id=style_id
        )
        job.zip_bytes = zip_bytes
        job.zip_name = zip_name
        job.status = "done"
        job.message = "生成完成"
    except ModelGenerationError as e:
        job.status = "error"
        job.error = str(e)
        job.message = str(e)
    except Exception:
        job.status = "error"
        job.error = "批量生成时发生内部错误"
        job.message = job.error
