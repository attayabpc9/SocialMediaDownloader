"""Validation for URLs accepted by the external download worker."""

from urllib.parse import urlparse


SUPPORTED_HOSTS = {
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'instagram.com', 'www.instagram.com',
    'facebook.com', 'www.facebook.com', 'fb.watch',
    'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com',
}


def detect_platform(url):
    parsed = urlparse(url.strip())
    if parsed.scheme != 'https' or not parsed.hostname:
        return 'unknown'

    hostname = parsed.hostname.lower().rstrip('.')
    if parsed.username or parsed.password or parsed.port or parsed.fragment:
        return 'unknown'
    if hostname not in SUPPORTED_HOSTS:
        return 'unknown'
    if hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}:
        return 'youtube'
    if hostname in {'instagram.com', 'www.instagram.com'}:
        return 'instagram'
    if hostname in {'facebook.com', 'www.facebook.com', 'fb.watch'}:
        return 'facebook'
    if hostname in {'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com'}:
        return 'tiktok'
    return 'unknown'
