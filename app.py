"""Lightweight VidzFlow web service.

The web service validates requests and coordinates jobs through the database.
The Render worker performs downloading and storage.
"""

import json
import uuid

from flask import Flask, jsonify, render_template, request
from sqlalchemy import func, select, text

from anonymous_jobs import issue_job_token, read_job_token
from config import MAX_ACTIVE_JOBS, MAX_REQUEST_BYTES, MAX_URL_LENGTH, SECRET_KEY
from database import SessionLocal, init_db
from models import Job
from url_validation import detect_platform


SUPPORTED_PLATFORMS = {'youtube', 'tiktok', 'instagram', 'facebook'}
MAX_BULK_URLS = 10


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=SECRET_KEY,
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
    )
    init_db()

    @app.after_request
    def add_security_headers(response):
        if request.path == '/':
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault(
            'Permissions-Policy', 'camera=(), microphone=(), geolocation=()'
        )
        return response

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/privacy')
    def privacy_page():
        return render_template('privacy.html')

    @app.get('/terms')
    def terms_page():
        return render_template('terms.html')

    @app.get('/health')
    def health():
        with SessionLocal() as session:
            session.execute(text('SELECT 1'))
        return jsonify({'status': 'ok'})

    @app.post('/download')
    def download():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid request.'}), 400

        url = str(data.get('url', '')).strip()
        if len(url) > MAX_URL_LENGTH:
            return jsonify({'status': 'error', 'message': 'URL is too long.'}), 413
        platform = detect_platform(url)
        if platform not in SUPPORTED_PLATFORMS:
            return jsonify({
                'status': 'error',
                'message': 'Only supported HTTPS media URLs are accepted.',
            }), 400

        with SessionLocal.begin() as session:
            active_jobs = session.scalar(
                select(func.count()).select_from(Job).where(
                    Job.status.in_(['queued', 'processing'])
                )
            )
            if active_jobs >= MAX_ACTIVE_JOBS:
                return jsonify({
                    'status': 'error',
                    'message': 'The service is busy. Please try again shortly.',
                }), 429
            job_id = uuid.uuid4().hex
            session.add(Job(
                id=job_id,
                source_url=url,
                platform=platform,
                status='queued',
                selected_format=data.get('format') or None,
            ))
        return jsonify({
            'status': 'queued',
            'job_id': job_id,
            'job_token': issue_job_token(job_id),
            'platform': platform,
        }), 202

    @app.get('/jobs/<job_token>')
    def job_status(job_token):
        job_id = read_job_token(job_token)
        if not job_id:
            return jsonify({'status': 'error', 'message': 'Invalid or expired job token.'}), 404
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job:
                return jsonify({'status': 'error', 'message': 'Job not found.'}), 404
            result = {
                'job_id': job.id,
                'status': job.status,
                'filename': job.filename,
                'title': job.title,
                'thumbnail': job.thumbnail_url,
                'progress': job.progress,
                'total_bytes': job.total_bytes,
            }
            if job.available_formats:
                result['formats'] = json.loads(job.available_formats)
            if job.file_url:
                result['file_url'] = job.file_url
            if job.error_message:
                result['message'] = job.error_message
            return jsonify(result)

    @app.post('/preview')
    def preview():
        data = request.get_json(silent=True)
        url = str(data.get('url', '')).strip(
        ) if isinstance(data, dict) else ''
        platform = detect_platform(url)
        if len(url) > MAX_URL_LENGTH or platform not in SUPPORTED_PLATFORMS:
            return jsonify({'status': 'error', 'message': 'Only supported HTTPS media URLs are accepted.'}), 400
        with SessionLocal.begin() as session:
            active_jobs = session.scalar(
                select(func.count()).select_from(Job).where(
                    Job.status.in_(['queued', 'processing', 'preview'])
                )
            )
            if active_jobs >= MAX_ACTIVE_JOBS:
                return jsonify({'status': 'error', 'message': 'The service is busy. Please try again shortly.'}), 429
            job_id = uuid.uuid4().hex
            session.add(Job(id=job_id, source_url=url,
                        platform=platform, status='preview'))
        return jsonify({
            'status': 'queued',
            'job_id': job_id,
            'job_token': issue_job_token(job_id),
            'platform': platform,
        }), 202

    @app.post('/download-quality')
    def download_quality():
        data = request.get_json(silent=True)
        token = data.get('job_token') if isinstance(data, dict) else None
        format_id = str(data.get('quality', '')).strip(
        ) if isinstance(data, dict) else ''
        job_id = read_job_token(token)
        if not job_id or not format_id or len(format_id) > 64:
            return jsonify({'status': 'error', 'message': 'A valid job and format are required.'}), 400
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            if not job or job.status != 'awaiting_format':
                return jsonify({'status': 'error', 'message': 'The preview is not ready.'}), 409
            formats = json.loads(job.available_formats or '[]')
            if not any(str(item.get('id')) == format_id for item in formats):
                return jsonify({'status': 'error', 'message': 'That format is not available.'}), 400
            job.selected_format = format_id
            job.status = 'queued'
        return jsonify({'status': 'queued', 'job_token': token}), 202

    @app.post('/bulk-download')
    def bulk_download():
        data = request.get_json(silent=True)
        urls = data.get('urls') if isinstance(data, dict) else None
        if not isinstance(urls, list) or not urls:
            return jsonify({'status': 'error', 'message': 'A URLs list is required.'}), 400
        if len(urls) > MAX_BULK_URLS:
            return jsonify({
                'status': 'error',
                'message': f'At most {MAX_BULK_URLS} URLs may be submitted at once.',
            }), 413

        results = []
        with SessionLocal.begin() as session:
            for raw_url in urls:
                url = str(raw_url).strip()
                if len(url) > MAX_URL_LENGTH:
                    results.append({
                        'status': 'error',
                        'url': url,
                        'message': 'URL is too long.',
                    })
                    continue
                platform = detect_platform(url)
                if platform not in SUPPORTED_PLATFORMS:
                    results.append({
                        'status': 'error',
                        'url': url,
                        'message': 'Unsupported or invalid HTTPS media URL.',
                    })
                    continue
                job_id = uuid.uuid4().hex
                active_jobs = session.scalar(
                    select(func.count()).select_from(Job).where(
                        Job.status.in_(['queued', 'processing'])
                    )
                )
                if active_jobs >= MAX_ACTIVE_JOBS:
                    results.append({
                        'status': 'error',
                        'url': url,
                        'message': 'The service is busy. Please try again shortly.',
                    })
                    continue
                session.add(Job(id=job_id, source_url=url, platform=platform))
                results.append({
                    'status': 'queued',
                    'job_id': job_id,
                    'job_token': issue_job_token(job_id),
                    'url': url,
                    'platform': platform,
                })
        return jsonify({
            'status': 'accepted',
            'message': f'Accepted {len(results)} URLs.',
            'results': results,
        }), 202

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
