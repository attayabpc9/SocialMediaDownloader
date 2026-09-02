"""Short-lived anonymous tokens for external worker jobs."""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import JOB_TOKEN_MAX_AGE, SECRET_KEY


_serializer = URLSafeTimedSerializer(SECRET_KEY)


def issue_job_token(job_id):
    return _serializer.dumps({'job_id': str(job_id)})


def read_job_token(token):
    if not token:
        return None
    try:
        payload = _serializer.loads(token, max_age=JOB_TOKEN_MAX_AGE)
        job_id = payload.get('job_id')
        return job_id if job_id else None
    except (BadSignature, SignatureExpired, TypeError, AttributeError, ValueError):
        return None
