"""Render background worker for yt-dlp downloads and S3-compatible storage."""

import logging
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import yt_dlp
from sqlalchemy import select

from config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    S3_PRESIGNED_URL_SECONDS,
    JOB_RETENTION_SECONDS,
    CLEANUP_INTERVAL_SECONDS,
    WORKER_JOB_TIMEOUT_SECONDS,
    WORKER_MAX_ATTEMPTS,
    MAX_DOWNLOAD_BYTES,
    FFMPEG_PATH,
    WORKER_POLL_SECONDS,
)
from database import SessionLocal, init_db
from models import Job

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def media_tool_directory():
    configured = Path(FFMPEG_PATH) if FFMPEG_PATH else None
    if configured:
        if configured.is_file():
            return configured.parent
        if (configured / 'ffmpeg.exe').is_file() or (configured / 'ffmpeg').is_file():
            return configured

    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return Path(ffmpeg).parent

    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        packages = Path(local_app_data) / 'Microsoft' / 'WinGet' / 'Packages'
        for candidate in packages.glob('Gyan.FFmpeg*'):
            for executable in candidate.rglob('ffmpeg.exe'):
                return executable.parent
    return None


def require_media_tools():
    directory = media_tool_directory()
    if not directory:
        raise RuntimeError(
            'FFmpeg and FFprobe are required. Install FFmpeg or set FFMPEG_PATH.'
        )
    ffmpeg_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    ffprobe_name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
    ffmpeg = directory / ffmpeg_name
    ffprobe = directory / ffprobe_name
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise RuntimeError(
            'Both ffmpeg and ffprobe must be available in FFMPEG_PATH.'
        )
    return directory, ffmpeg, ffprobe


def storage_client():
    if not all((S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY)):
        raise RuntimeError(
            'S3_BUCKET, S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required')
    if not S3_ENDPOINT_URL and (
        S3_REGION == 'auto' or S3_REGION.startswith('your-')
    ):
        raise RuntimeError(
            'Set S3_REGION to your real AWS region, such as us-east-1')
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL or None,
        region_name=S3_REGION or None,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )


def claim_job():
    with SessionLocal.begin() as session:
        stale_jobs = session.scalars(
            select(Job).where(
                Job.status == 'processing',
                Job.updated_at < datetime.now(timezone.utc) - timedelta(
                    seconds=WORKER_JOB_TIMEOUT_SECONDS
                )
            )
        ).all()
        for stale_job in stale_jobs:
            if stale_job.attempts < WORKER_MAX_ATTEMPTS:
                stale_job.status = 'queued'
            else:
                stale_job.status = 'failed'
                stale_job.error_message = 'The worker timed out repeatedly.'

        job = session.scalar(
            select(Job)
            .where(Job.status.in_(['queued', 'preview']))
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status = 'processing'
        job.attempts += 1
        return job.id


def cleanup_expired_jobs():
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=JOB_RETENTION_SECONDS
    )
    client = None
    with SessionLocal() as session:
        jobs = session.scalars(
            select(Job).where(
                Job.status.in_([
                    'ready',
                    'failed',
                    'preview',
                    'awaiting_format',
                    'queued',
                ]),
                Job.updated_at < cutoff,
            ).limit(50)
        ).all()
        for job in jobs:
            if job.status == 'ready' and job.filename:
                if client is None:
                    try:
                        client = storage_client()
                    except Exception:
                        logger.exception(
                            'Could not connect to storage for job %s', job.id)
                        continue
                object_key = f'jobs/{job.id}/{job.filename}'
                try:
                    client.delete_object(Bucket=S3_BUCKET, Key=object_key)
                except Exception:
                    logger.exception(
                        'Could not delete object for job %s', job.id)
                    continue
            try:
                session.delete(job)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception(
                    'Could not delete database record for job %s', job.id)


def cleanup_orphan_objects():
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=JOB_RETENTION_SECONDS
    )
    client = storage_client()
    paginator = client.get_paginator('list_objects_v2')
    with SessionLocal() as session:
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix='jobs/'):
            for item in page.get('Contents', []):
                object_key = item.get('Key', '')
                modified_at = item.get('LastModified')
                parts = object_key.split('/', 2)
                if len(parts) != 3 or not modified_at or modified_at >= cutoff:
                    continue
                job = session.get(Job, parts[1])
                if job and job.status == 'ready' and job.filename == parts[2]:
                    continue
                try:
                    client.delete_object(Bucket=S3_BUCKET, Key=object_key)
                except Exception:
                    logger.exception(
                        'Could not delete orphan object %s', object_key)


def process_job(job_id):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            return
        source_url = job.source_url
        platform = job.platform
        selected_format = job.selected_format

    work_dir = Path(tempfile.mkdtemp(prefix=f'vidzflow-{job_id}-'))
    try:
        media_tools, _, ffprobe = require_media_tools()
        output_template = str(work_dir / '%(title).120s-%(id)s.%(ext)s')
        last_progress_update = [0.0]

        def progress_hook(event):
            if event.get('status') != 'downloading':
                return
            now = time.monotonic()
            if now - last_progress_update[0] < 1:
                return
            last_progress_update[0] = now
            total = event.get('total_bytes') or event.get(
                'total_bytes_estimate')
            downloaded = event.get('downloaded_bytes', 0)
            progress = int(downloaded * 100 / total) if total else 0
            with SessionLocal.begin() as session:
                job = session.get(Job, job_id)
                if job and job.status == 'processing':
                    job.progress = min(progress, 99)
                    job.total_bytes = total

        if not selected_format:
            with yt_dlp.YoutubeDL({
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': WORKER_JOB_TIMEOUT_SECONDS,
                'ffmpeg_location': str(media_tools),
            }) as downloader:
                info = downloader.extract_info(source_url, download=False)
            formats = []
            for item in info.get('formats', []):
                if not item.get('format_id') or not item.get('vcodec') or item.get('vcodec') == 'none':
                    continue
                formats.append({
                    'id': str(item['format_id']),
                    'label': f"{item.get('height') or '?'}p {item.get('ext', '').upper()}",
                    'detail': f"{item.get('resolution') or 'video'} / {item.get('fps') or '?'} fps",
                })
            if not formats:
                formats.append({
                    'id': 'best',
                    'label': 'Best available',
                    'detail': 'Automatic playable MP4',
                })
            unique_formats = {item['id']: item for item in formats}
            with SessionLocal.begin() as session:
                job = session.get(Job, job_id)
                if job:
                    job.title = info.get('title') or 'Video'
                    job.thumbnail_url = info.get('thumbnail')
                    job.available_formats = json.dumps(
                        list(unique_formats.values()))
                    job.status = 'awaiting_format'
                    job.progress = 0
            return

        format_selector = (
            'bestvideo*+bestaudio/best'
            if selected_format == 'best'
            else f'{selected_format}+bestaudio/best'
        )
        options = {
            'format': format_selector,
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'retries': 2,
            'fragment_retries': 2,
            'max_filesize': MAX_DOWNLOAD_BYTES,
            'socket_timeout': WORKER_JOB_TIMEOUT_SECONDS,
            'ffmpeg_location': str(media_tools),
            'progress_hooks': [progress_hook],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source_url, download=True)

        files = [
            path for path in work_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {'.mp4', '.webm', '.mkv'}
        ]
        if not files:
            raise RuntimeError('The worker did not produce a file')
        source_file = max(files, key=lambda path: path.stat().st_size)
        if source_file.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise RuntimeError('The downloaded file exceeds the size limit')
        normalized_file = work_dir / 'vidzflow-normalized.mp4'
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            if job and job.status == 'processing':
                job.progress = 95

        normalize = subprocess.run(
            [
                str(media_tools / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')),
                '-y', '-hide_banner', '-loglevel', 'error',
                '-i', str(source_file), '-map', '0:v:0', '-map', '0:a:0?',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart', str(normalized_file),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if normalize.returncode != 0 or not normalized_file.is_file():
            raise RuntimeError('FFmpeg could not create a playable MP4 file')
        source_file = normalized_file
        if source_file.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise RuntimeError('The converted file exceeds the size limit')
        probe = subprocess.run(
            [
                str(ffprobe), '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=nw=1:nk=1', str(source_file),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0 or probe.stdout.strip() != 'h264':
            raise RuntimeError('The worker produced an unreadable video')
        filename = f'{uuid.uuid4().hex}-{source_file.name}'
        object_key = f'jobs/{job_id}/{filename}'
        client = storage_client()
        content_type = mimetypes.guess_type(source_file.name)[
            0] or 'application/octet-stream'
        client.upload_file(
            str(source_file),
            S3_BUCKET,
            object_key,
            ExtraArgs={'ContentType': content_type},
        )
        try:
            file_url = client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET,
                    'Key': object_key,
                    'ResponseContentType': 'video/mp4',
                    'ResponseContentDisposition': (
                        f'attachment; filename="{filename}"'
                    ),
                },
                ExpiresIn=min(S3_PRESIGNED_URL_SECONDS, JOB_RETENTION_SECONDS),
            )
            with SessionLocal.begin() as session:
                job = session.get(Job, job_id)
                if not job:
                    raise RuntimeError('The job record no longer exists')
                job.status = 'ready'
                job.progress = 100
                job.title = info.get('title') or job.title
                job.thumbnail_url = info.get('thumbnail') or job.thumbnail_url
                job.filename = filename
                job.file_url = file_url
                job.error_message = None
        except Exception:
            try:
                client.delete_object(Bucket=S3_BUCKET, Key=object_key)
            except Exception:
                logger.exception(
                    'Could not roll back object for job %s', job_id)
            raise
        logger.info('Completed job %s (%s)', job_id, platform)
    except Exception as error:
        logger.exception('Job %s failed', job_id)
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = 'failed'
                job.error_message = 'The worker could not process this download.'
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run():
    init_db()
    next_cleanup = 0.0
    while True:
        now = time.monotonic()
        if now >= next_cleanup:
            try:
                cleanup_expired_jobs()
                cleanup_orphan_objects()
            except Exception:
                logger.exception(
                    'Storage cleanup cycle failed; continuing worker loop')
            next_cleanup = now + CLEANUP_INTERVAL_SECONDS
        job_id = claim_job()
        if job_id:
            process_job(job_id)
        else:
            time.sleep(WORKER_POLL_SECONDS)


if __name__ == '__main__':
    run()
