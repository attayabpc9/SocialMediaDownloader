"""Application settings loaded from environment variables."""

import os

from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'sqlite:///vidzflow.db'
)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace(
        'postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace(
        'postgresql://', 'postgresql+psycopg://', 1)

SECRET_KEY = os.environ.get(
    'VIDZFLOW_SECRET_KEY',
    'development-only-change-this-secret'
)
IS_PRODUCTION = not DATABASE_URL.startswith('sqlite')
if IS_PRODUCTION and (
    SECRET_KEY == 'development-only-change-this-secret'
    or len(SECRET_KEY) < 32
):
    raise RuntimeError(
        'VIDZFLOW_SECRET_KEY must be at least 32 characters in production'
    )
JOB_TOKEN_MAX_AGE = int(
    os.environ.get('VIDZFLOW_JOB_TOKEN_MAX_AGE', '1800')
)
MAX_REQUEST_BYTES = int(
    os.environ.get('VIDZFLOW_MAX_REQUEST_BYTES', str(64 * 1024))
)
S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL', '')
S3_REGION = os.environ.get(
    'S3_REGION',
    os.environ.get('AWS_REGION', 'auto')
)
S3_BUCKET = os.environ.get('S3_BUCKET', '')
S3_ACCESS_KEY_ID = os.environ.get('S3_ACCESS_KEY_ID', '')
S3_SECRET_ACCESS_KEY = os.environ.get('S3_SECRET_ACCESS_KEY', '')
WORKER_POLL_SECONDS = float(os.environ.get('WORKER_POLL_SECONDS', '2'))
S3_PRESIGNED_URL_SECONDS = int(
    os.environ.get('S3_PRESIGNED_URL_SECONDS', '1800')
)
JOB_RETENTION_SECONDS = int(
    os.environ.get('JOB_RETENTION_SECONDS', '1800')
)
CLEANUP_INTERVAL_SECONDS = int(
    os.environ.get('CLEANUP_INTERVAL_SECONDS', '300')
)
WORKER_JOB_TIMEOUT_SECONDS = int(
    os.environ.get('WORKER_JOB_TIMEOUT_SECONDS', '900')
)
WORKER_MAX_ATTEMPTS = int(os.environ.get('WORKER_MAX_ATTEMPTS', '3'))
MAX_ACTIVE_JOBS = int(os.environ.get('MAX_ACTIVE_JOBS', '20'))
MAX_URL_LENGTH = int(os.environ.get('MAX_URL_LENGTH', '2048'))
MAX_DOWNLOAD_BYTES = int(
    os.environ.get('MAX_DOWNLOAD_BYTES', str(500 * 1024 * 1024))
)
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', '')
