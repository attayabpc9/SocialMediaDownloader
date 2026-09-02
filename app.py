from flask import Flask, request, render_template, jsonify, send_file
import os
import tempfile
import requests
import re
from datetime import datetime
import yt_dlp
import instaloader
from werkzeug.utils import secure_filename
import zipfile
import shutil
import subprocess

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'


# =============================================================
# DOWNLOAD DIRECTORY
# =============================================================

DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


# =============================================================
# UNIVERSAL DOWNLOADER
# =============================================================

class UniversalDownloader:

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/139.0.0.0 Safari/537.36'
            )
        })


    # =========================================================
    # PLATFORM DETECTION
    # =========================================================

    def detect_platform(self, url):

        url = url.lower().strip()

        if 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'

        elif 'instagram.com' in url:
            return 'instagram'

        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'

        elif 'tiktok.com' in url:
            return 'tiktok'

        else:
            return 'unknown'


    # =========================================================
    # SAFE FILENAME
    # =========================================================

    def create_safe_filename(self, filename, max_length=100):

        filename = str(filename)

        filename = re.sub(
            r'[<>:"/\\|?*]',
            '_',
            filename
        )

        filename = re.sub(
            r'[\x00-\x1f]',
            '',
            filename
        )

        filename = filename.strip()

        filename = filename.rstrip('. ')

        if not filename:
            filename = 'download'

        if len(filename) > max_length:
            filename = filename[:max_length]

        return filename


    # =========================================================
    # FFMPEG / MP4 COMPATIBILITY
    # =========================================================
    def get_ffmpeg_path(self):
        found = shutil.which("ffmpeg")
        if found:
            return found
        candidates = [
            os.environ.get("FFMPEG_PATH"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Users\Abdullah\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        return None

    def ensure_mp4_compatible(self, folder):
        """Create device-friendly MP4 files using H.264 video and AAC audio."""
        ffmpeg = self.get_ffmpeg_path()
        if not ffmpeg:
            return {
                'status': 'error',
                'message': 'FFmpeg is required to create compatible MP4 (H.264/AAC) files. Install FFmpeg and add it to PATH.'
            }

        video_exts = {'.webm', '.mkv', '.mov', '.avi', '.flv', '.ts', '.m4v', '.mp4'}
        converted = []

        for root, _, files in os.walk(folder):
            for name in files:
                source = os.path.join(root, name)
                ext = os.path.splitext(name)[1].lower()
                if ext not in video_exts or name.startswith('._'):
                    continue

                target = os.path.splitext(source)[0] + '.mp4'
                temp_target = target + '.tmp.mp4'

                cmd = [
                    ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', source, '-map', '0:v:0', '-map', '0:a:0?',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart', temp_target
                ]
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                    if proc.returncode != 0 or not os.path.exists(temp_target) or os.path.getsize(temp_target) < 1024:
                        if os.path.exists(temp_target):
                            os.remove(temp_target)
                        return {'status': 'error', 'message': 'FFmpeg could not convert the downloaded video to a compatible MP4.'}
                    if os.path.exists(target) and os.path.abspath(source) != os.path.abspath(target):
                        os.remove(target)
                    os.replace(temp_target, target)
                    if os.path.abspath(source) != os.path.abspath(target) and os.path.exists(source):
                        os.remove(source)
                    converted.append(os.path.abspath(target))
                except subprocess.TimeoutExpired:
                    if os.path.exists(temp_target):
                        os.remove(temp_target)
                    return {'status': 'error', 'message': 'MP4 conversion timed out. Please try again.'}
                except Exception as e:
                    if os.path.exists(temp_target):
                        os.remove(temp_target)
                    return {'status': 'error', 'message': f'MP4 conversion error: {str(e)}'}

        if not converted:
            return {'status': 'error', 'message': 'No video file was produced by the downloader.'}
        return {'status': 'success', 'files': converted}


    # =========================================================
    # YOUTUBE
    # =========================================================

    def download_youtube_content(self, url, path):

        try:

            # -------------------------------------------------
            # Find FFmpeg
            # -------------------------------------------------

            ffmpeg_path = self.get_ffmpeg_path()


            # -------------------------------------------------
            # yt-dlp options
            # -------------------------------------------------

            ydl_opts = {

                'outtmpl': os.path.join(
                    path,
                    '%(uploader)s - %(title)s.%(ext)s'
                ),

                # Best available video + audio
                # with fallback
                'format': (
                    'bestvideo*+bestaudio/'
                    'best'
                ),

                'merge_output_format': 'mp4',

                'writesubtitles': False,

                'writeautomaticsub': False,

                'ignoreerrors': False,

                'noplaylist': False,

                'quiet': False,

                'no_warnings': False,

                'retries': 3,

                'fragment_retries': 3,

            }


            # -------------------------------------------------
            # Add FFmpeg only if found
            # -------------------------------------------------

            if ffmpeg_path:

                ydl_opts['ffmpeg_location'] = ffmpeg_path


            # -------------------------------------------------
            # IMPORTANT
            #
            # Do NOT use:
            #
            # 'js_runtimes': {
            #     'deno': ...
            # }
            #
            # This was causing:
            #
            # Invalid js_runtimes format
            # -------------------------------------------------


            # -------------------------------------------------
            # Download
            # -------------------------------------------------

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )


            if info is None:

                return {
                    'status': 'error',
                    'message': (
                        'Could not extract YouTube '
                        'video information.'
                    )
                }


            # -------------------------------------------------
            # Playlist
            # -------------------------------------------------

            if info.get('entries') is not None:

                entries = [
                    entry
                    for entry in info.get('entries', [])
                    if entry is not None
                ]

                titles = [
                    entry.get(
                        'title',
                        'Unknown'
                    )
                    for entry in entries
                ]

                return {

                    'status': 'success',

                    'message': (
                        f'Downloaded {len(titles)} '
                        f'videos from playlist'
                    ),

                    'titles': titles[:5],

                    'type': 'playlist'

                }


            # -------------------------------------------------
            # Single video
            # -------------------------------------------------

            return {

                'status': 'success',

                'message': (
                    'YouTube content downloaded '
                    'successfully!'
                ),

                'title': info.get(
                    'title',
                    'Unknown'
                ),

                'uploader': info.get(
                    'uploader',
                    'Unknown'
                ),

                'type': 'video'

            }


        except yt_dlp.utils.DownloadError as e:

            return {

                'status': 'error',

                'message': (
                    f'YouTube download failed: {str(e)}'
                )

            }


        except Exception as e:

            return {

                'status': 'error',

                'message': (
                    f'YouTube error: {str(e)}'
                )

            }


    # =========================================================
    # INSTAGRAM
    # =========================================================

    def download_instagram_content(self, url, path):

        try:

            loader = instaloader.Instaloader(

                dirname_pattern=path,

                filename_pattern=(
                    '{profile}_{mediaid}_{date_utc}'
                ),

                download_videos=True,

                download_video_thumbnails=False,

                download_geotags=False,

                download_comments=False,

                save_metadata=True,

                compress_json=False

            )


            # -------------------------------------------------
            # Instagram Stories
            # -------------------------------------------------

            if '/stories/' in url:

                username = self.extract_instagram_username(
                    url
                )

                if not username:

                    return {
                        'status': 'error',
                        'message': (
                            'Could not extract '
                            'Instagram username.'
                        )
                    }


                profile = instaloader.Profile.from_username(
                    loader.context,
                    username
                )


                for story in loader.get_stories(
                    [profile.userid]
                ):

                    for item in story.get_items():

                        loader.download_storyitem(
                            item,
                            target=username
                        )


                return {

                    'status': 'success',

                    'message': (
                        f'Instagram stories downloaded '
                        f'for {username}'
                    ),

                    'type': 'stories'

                }


            # -------------------------------------------------
            # Reel / Post / IGTV
            # -------------------------------------------------

            elif (
                '/reel/' in url
                or '/p/' in url
                or '/tv/' in url
            ):

                shortcode = (
                    self.extract_instagram_shortcode(url)
                )


                if not shortcode:

                    return {

                        'status': 'error',

                        'message': (
                            'Could not extract '
                            'Instagram shortcode.'
                        )

                    }


                post = instaloader.Post.from_shortcode(
                    loader.context,
                    shortcode
                )


                loader.download_post(
                    post,
                    target=post.owner_username
                )


                content_type = (
                    'reel'
                    if post.is_video
                    else 'post'
                )


                if post.typename == 'GraphSidecar':

                    content_type = 'carousel'


                caption = post.caption or ''


                if len(caption) > 100:

                    caption = caption[:100] + '...'


                return {

                    'status': 'success',

                    'message': (
                        f'Instagram {content_type} '
                        f'downloaded successfully!'
                    ),

                    'username': (
                        post.owner_username
                    ),

                    'caption': caption,

                    'type': content_type

                }


            # -------------------------------------------------
            # Instagram Profile
            # -------------------------------------------------

            else:

                username = (
                    self.extract_instagram_username(url)
                )


                if not username:

                    return {

                        'status': 'error',

                        'message': (
                            'Could not extract '
                            'Instagram username.'
                        )

                    }


                profile = (
                    instaloader.Profile.from_username(
                        loader.context,
                        username
                    )
                )


                count = 0


                for post in profile.get_posts():

                    if count >= 10:

                        break


                    loader.download_post(
                        post,
                        target=username
                    )

                    count += 1


                return {

                    'status': 'success',

                    'message': (
                        f'Downloaded {count} recent '
                        f'posts from {username}'
                    ),

                    'type': 'profile'

                }


        except Exception as e:

            return {

                'status': 'error',

                'message': (
                    f'Instagram error: {str(e)}'
                )

            }


        # =========================================================
    # TIKTOK
    # =========================================================
    def download_tiktok_content(self, url, path):
        """
        TikTok downloader using TikWM API.

        yt-dlp TikTok extractor is currently returning:
        "Unexpected response from webpage request"

        Therefore TikTok is handled separately.
        YouTube / Instagram / Facebook remain unchanged.
        """

        try:
            # -------------------------------------------------
            # TikWM API
            # -------------------------------------------------
            api_url = "https://www.tikwm.com/api/"

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/139.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "application/json, text/plain, */*"
                ),
                "Referer": "https://www.tikwm.com/"
            }

            # -------------------------------------------------
            # Resolve TikTok URL
            # -------------------------------------------------
            response = self.session.post(
                api_url,
                data={
                    "url": url,
                    "hd": 1
                },
                headers=headers,
                timeout=40
            )

            response.raise_for_status()

            # -------------------------------------------------
            # Parse JSON
            # -------------------------------------------------
            try:
                data = response.json()

            except ValueError:
                return {
                    "status": "error",
                    "message": (
                        "TikTok API returned an invalid response."
                    )
                }

            # -------------------------------------------------
            # Validate API response
            # -------------------------------------------------
            if not isinstance(data, dict):
                return {
                    "status": "error",
                    "message": (
                        "Invalid TikTok API response."
                    )
                }

            if data.get("code") != 0:
                return {
                    "status": "error",
                    "message": (
                        data.get(
                            "msg",
                            "TikTok video could not be resolved."
                        )
                    )
                }

            video_data = data.get("data")

            if not isinstance(video_data, dict):
                return {
                    "status": "error",
                    "message": (
                        "TikTok video information "
                        "was not found."
                    )
                }

            # -------------------------------------------------
            # Get video URL
            #
            # play = no watermark
            # hdplay = HD version
            # wmplay = watermark version
            #
            # Prefer play because hdplay can sometimes be
            # returned as HEVC/H.265.
            # -------------------------------------------------
            video_url = (
                video_data.get("play")
                or video_data.get("hdplay")
                or video_data.get("wmplay")
            )

            if not video_url:
                return {
                    "status": "error",
                    "message": (
                        "TikTok video download URL "
                        "was not found."
                    )
                }

            # -------------------------------------------------
            # Metadata
            # -------------------------------------------------
            title = (
                video_data.get("title")
                or "TikTok Video"
            )

            author_data = video_data.get("author")

            if isinstance(author_data, dict):
                uploader = (
                    author_data.get("unique_id")
                    or author_data.get("nickname")
                    or "TikTok"
                )
            else:
                uploader = "TikTok"

            video_id = (
                video_data.get("id")
                or "video"
            )

            # -------------------------------------------------
            # Clean filename
            # -------------------------------------------------
            safe_title = self.create_safe_filename(
                title,
                max_length=80
            )

            safe_uploader = self.create_safe_filename(
                uploader,
                max_length=40
            )

            safe_video_id = self.create_safe_filename(
                video_id,
                max_length=40
            )

            filename = (
                f"TikTok_{safe_uploader}_"
                f"{safe_title}_{safe_video_id}.mp4"
            )

            file_path = os.path.join(
                path,
                filename
            )

            # -------------------------------------------------
            # Download headers
            # -------------------------------------------------
            video_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/139.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.tiktok.com/",
                "Accept": "*/*"
            }

            # -------------------------------------------------
            # Download actual MP4
            # -------------------------------------------------
            with self.session.get(
                video_url,
                headers=video_headers,
                stream=True,
                timeout=90,
                allow_redirects=True
            ) as video_response:

                video_response.raise_for_status()

                content_type = (
                    video_response.headers.get(
                        "Content-Type",
                        ""
                    ).lower()
                )

                # -------------------------------------------------
                # Open file
                # -------------------------------------------------
                with open(
                    file_path,
                    "wb"
                ) as video_file:

                    total_size = 0

                    for chunk in video_response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if not chunk:
                            continue

                        video_file.write(chunk)
                        total_size += len(chunk)

            # -------------------------------------------------
            # Verify downloaded file
            # -------------------------------------------------
            if not os.path.exists(file_path):
                return {
                    "status": "error",
                    "message": (
                        "TikTok video file "
                        "was not created."
                    )
                }

            file_size = os.path.getsize(file_path)

            if file_size < 1024:
                try:
                    os.remove(file_path)
                except Exception:
                    pass

                return {
                    "status": "error",
                    "message": (
                        "TikTok returned an empty "
                        "or invalid video file."
                    )
                }

            # -------------------------------------------------
            # Success
            # -------------------------------------------------
            return {
                "status": "success",
                "message": (
                    "TikTok video downloaded "
                    "successfully!"
                ),
                "title": title,
                "uploader": uploader,
                "filename": filename,
                "filesize": file_size,
                "type": "video"
            }

        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "message": (
                    "TikTok request timed out. "
                    "Please try again."
                )
            }

        except requests.exceptions.HTTPError as e:
            return {
                "status": "error",
                "message": (
                    f"TikTok HTTP error: {str(e)}"
                )
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": (
                    f"TikTok network error: {str(e)}"
                )
            }

        except Exception as e:
            return {
                "status": "error",
                "message": (
                    f"TikTok error: {str(e)}"
                )
            }
    # =========================================================
    # FACEBOOK
    # =========================================================

    def download_facebook_content(self, url, path):

        try:

            ydl_opts = {

                'outtmpl': os.path.join(
                    path,
                    'Facebook_%(title)s.%(ext)s'
                ),

                'format': 'best'

            }


            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )


                if info is None:

                    return {

                        'status': 'error',

                        'message': (
                            'Facebook content '
                            'could not be extracted.'
                        )

                    }


                return {

                    'status': 'success',

                    'message': (
                        'Facebook content downloaded '
                        'successfully!'
                    ),

                    'title': info.get(
                        'title',
                        'Facebook Content'
                    ),

                    'type': 'video'

                }


        except Exception as e:

            return {

                'status': 'error',

                'message': (
                    f'Facebook error: {str(e)}'
                )

            }


    # =========================================================
    # INSTAGRAM SHORTCODE
    # =========================================================

    def extract_instagram_shortcode(self, url):

        patterns = [

            r'/p/([^/?]+)',

            r'/reel/([^/?]+)',

            r'/tv/([^/?]+)'

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                url
            )


            if match:

                return match.group(1)


        return None


    # =========================================================
    # INSTAGRAM USERNAME
    # =========================================================

    def extract_instagram_username(self, url):

        match = re.search(
            r'instagram\.com/([^/?]+)',
            url,
            re.IGNORECASE
        )


        if match:

            username = match.group(1)


            if username.lower() in [

                'p',
                'reel',
                'reels',
                'tv',
                'stories',
                'explore'

            ]:

                return None


            return username


        return None


    # =========================================================
    # MAIN DOWNLOAD FUNCTION
    # =========================================================

    def download_content(
        self,
        url,
        custom_path=None
    ):

        """
        Main downloader dispatcher.

        IMPORTANT:
        This method MUST remain inside
        UniversalDownloader class.
        """

        path = (
            custom_path
            or DOWNLOAD_DIR
        )


        platform = self.detect_platform(
            url
        )


        # -----------------------------------------------------
        # Only allow these 4 platforms
        # -----------------------------------------------------

        allowed_platforms = [

            'youtube',
            'tiktok',
            'instagram',
            'facebook'

        ]


        if platform not in allowed_platforms:

            return {

                'status': 'error',

                'message': (
                    'Unsupported platform. '
                    'Only YouTube, TikTok, '
                    'Instagram and Facebook '
                    'are supported.'
                )

            }


        # -----------------------------------------------------
        # Timestamp folder
        # -----------------------------------------------------

        timestamp = datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )


        download_folder = os.path.join(

            path,

            f'{platform}_{timestamp}'

        )


        os.makedirs(
            download_folder,
            exist_ok=True
        )


        # -----------------------------------------------------
        # Platform dispatcher
        # -----------------------------------------------------

        try:

            if platform == 'youtube':
                result = self.download_youtube_content(url, download_folder)
            elif platform == 'tiktok':
                result = self.download_tiktok_content(url, download_folder)
            elif platform == 'instagram':
                result = self.download_instagram_content(url, download_folder)
            elif platform == 'facebook':
                result = self.download_facebook_content(url, download_folder)
            else:
                result = {'status': 'error', 'message': 'Unsupported platform.'}

            if result.get('status') == 'success':
                mp4_result = self.ensure_mp4_compatible(download_folder)
                if mp4_result.get('status') != 'success':
                    return mp4_result
                rel_files = [
                    os.path.relpath(f, DOWNLOAD_DIR).replace('\\', '/')
                    for f in mp4_result['files']
                ]
                result['files'] = rel_files
                result['format'] = 'MP4 (H.264/AAC)'
                if len(rel_files) == 1:
                    result['filename'] = os.path.basename(mp4_result['files'][0])
                    result['file_url'] = '/media/' + rel_files[0]
                return result

            return result

        except Exception as e:

            return {

                'status': 'error',

                'message': (
                    f'Unexpected error: {str(e)}'
                )

            }


# =============================================================
# INITIALIZE DOWNLOADER
# =============================================================

downloader = UniversalDownloader()


# =============================================================
# HOME
# =============================================================

@app.route('/')
def index():

    return render_template(
        'index.html'
    )


# =============================================================
# INFORMATION PAGES
# =============================================================
@app.route('/about')
def about_page():
    return render_template('about')

@app.route('/faq')
def faq_page():
    return render_template('faq')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

@app.route('/terms')
def terms_page():
    return render_template('terms.html')

@app.route('/dmca')
def dmca_page():
    return render_template('dmca.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')


# =============================================================
# DOWNLOAD
# =============================================================

@app.route(
    '/download',
    methods=['POST']
)
def download():

    try:

        data = request.get_json()


        if not data:

            return jsonify({

                'status': 'error',

                'message': 'Invalid request.'

            })


        url = data.get(
            'url',
            ''
        ).strip()


        if not url:

            return jsonify({

                'status': 'error',

                'message': 'URL is required'

            })


        platform = downloader.detect_platform(
            url
        )


        # -----------------------------------------------------
        # Only 4 supported platforms
        # -----------------------------------------------------

        if platform not in [
            'youtube',
            'tiktok',
            'instagram',
            'facebook'
        ]:

            return jsonify({

                'status': 'error',

                'message': (
                    'Only YouTube, TikTok, '
                    'Instagram and Facebook '
                    'are supported.'
                ),

                'platform': platform

            })


        result = downloader.download_content(
            url
        )


        result['platform'] = platform


        return jsonify(result)


    except Exception as e:

        return jsonify({

            'status': 'error',

            'message': (
                f'Server error: {str(e)}'
            )

        })


# =============================================================
# BULK DOWNLOAD
# =============================================================

@app.route(
    '/bulk-download',
    methods=['POST']
)
def bulk_download():

    try:

        data = request.get_json()


        if not data:

            return jsonify({

                'status': 'error',

                'message': 'Invalid request.'

            })


        urls = data.get(
            'urls',
            []
        )


        if not urls:

            return jsonify({

                'status': 'error',

                'message': 'URLs list is required'

            })


        results = []


        for url in urls:

            url = url.strip()


            if not url:

                continue


            platform = downloader.detect_platform(
                url
            )


            if platform not in [
                'youtube',
                'tiktok',
                'instagram',
                'facebook'
            ]:

                results.append({

                    'status': 'error',

                    'message': (
                        'Unsupported platform'
                    ),

                    'url': url

                })

                continue


            result = downloader.download_content(
                url
            )


            result['url'] = url

            result['platform'] = platform


            results.append(result)


        return jsonify({

            'status': 'success',

            'message': (
                f'Processed {len(results)} URLs'
            ),

            'results': results

        })


    except Exception as e:

        return jsonify({

            'status': 'error',

            'message': (
                f'Bulk download error: {str(e)}'
            )

        })


# =============================================================
# LIST DOWNLOADS
# =============================================================

@app.route('/downloads')
def list_downloads():

    try:

        items = []


        if os.path.exists(
            DOWNLOAD_DIR
        ):

            for item in os.listdir(
                DOWNLOAD_DIR
            ):

                item_path = os.path.join(
                    DOWNLOAD_DIR,
                    item
                )


                if os.path.isfile(
                    item_path
                ):

                    items.append({

                        'name': item,

                        'type': 'file',

                        'size': os.path.getsize(
                            item_path
                        )

                    })


                elif os.path.isdir(
                    item_path
                ):

                    file_count = len([

                        f

                        for f in os.listdir(
                            item_path
                        )

                        if os.path.isfile(
                            os.path.join(
                                item_path,
                                f
                            )
                        )

                    ])


                    items.append({

                        'name': item,

                        'type': 'folder',

                        'file_count': file_count

                    })


        return jsonify({

            'items': items

        })


    except Exception as e:

        return jsonify({

            'error': str(e)

        })


# =============================================================
# DOWNLOAD FILE
# =============================================================

@app.route(
    '/download-file/<path:filename>'
)
def download_file(filename):

    try:

        safe_filename = secure_filename(
            filename
        )


        file_path = os.path.join(
            DOWNLOAD_DIR,
            safe_filename
        )


        if os.path.exists(
            file_path
        ):

            return send_file(
                file_path,
                as_attachment=True
            )


        return jsonify({

            'error': 'File not found'

        }), 404


    except Exception as e:

        return jsonify({

            'error': str(e)

        }), 500


# =============================================================
# DOWNLOAD FOLDER AS ZIP
# =============================================================

@app.route(
    '/download-folder/<foldername>'
)
def download_folder(foldername):

    try:

        safe_foldername = secure_filename(
            foldername
        )


        folder_path = os.path.join(
            DOWNLOAD_DIR,
            safe_foldername
        )


        if (
            os.path.exists(folder_path)
            and os.path.isdir(folder_path)
        ):

            temp_zip = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.zip'
            )


            temp_zip.close()


            with zipfile.ZipFile(
                temp_zip.name,
                'w',
                zipfile.ZIP_DEFLATED
            ) as zipf:

                for root, dirs, files in os.walk(
                    folder_path
                ):

                    for file in files:

                        file_path = os.path.join(
                            root,
                            file
                        )


                        arcname = os.path.relpath(
                            file_path,
                            folder_path
                        )


                        zipf.write(
                            file_path,
                            arcname
                        )


            return send_file(

                temp_zip.name,

                as_attachment=True,

                download_name=(
                    f'{safe_foldername}.zip'
                )

            )


        return jsonify({

            'error': 'Folder not found'

        }), 404


    except Exception as e:

        return jsonify({

            'error': str(e)

        }), 500


# =============================================================
# SERVE DOWNLOADED MEDIA
# =============================================================
@app.route('/media/<path:filename>')
def media_file(filename):
    try:
        safe_path = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
        base = os.path.abspath(DOWNLOAD_DIR)
        if not safe_path.startswith(base + os.sep) or not os.path.isfile(safe_path):
            return jsonify({'error': 'File not found'}), 404
        return send_file(safe_path, as_attachment=True, download_name=os.path.basename(safe_path), mimetype='video/mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================
# SUPPORTED PLATFORMS
# =============================================================

@app.route(
    '/supported-platforms'
)
def supported_platforms():

    platforms = {

        'video_platforms': [

            'YouTube (videos, shorts, playlists)',

            'TikTok',

            'Facebook',

            'Instagram (Reels, Posts, IGTV)'

        ],

        'social_platforms': [

            'Instagram (Posts, Stories, Reels, IGTV)',

            'Facebook (Posts, Videos)',

            'TikTok'

        ],

        'features': [

            'Auto-platform detection',

            'Bulk downloads',

            'Stories download',

            'Playlist support',

            'High quality downloads',

            'Metadata preservation'

        ]

    }


    return jsonify(
        platforms
    )


# =============================================================
# CLEAR DOWNLOADS
# =============================================================

@app.route(
    '/clear-downloads',
    methods=['POST']
)
def clear_downloads():

    try:

        if os.path.exists(
            DOWNLOAD_DIR
        ):

            shutil.rmtree(
                DOWNLOAD_DIR
            )


            os.makedirs(
                DOWNLOAD_DIR
            )


        return jsonify({

            'status': 'success',

            'message': (
                'Downloads cleared successfully'
            )

        })


    except Exception as e:

        return jsonify({

            'status': 'error',

            'message': (
                f'Error clearing downloads: {str(e)}'
            )

        })


# =============================================================
# RUN SERVER
# =============================================================

if __name__ == '__main__':

    print('=' * 60)

    print(
        'UNIVERSAL SOCIAL MEDIA DOWNLOADER'
    )

    print('=' * 60)

    print(
        'Supported platforms: '
        'YouTube, TikTok, Instagram, Facebook'
    )

    print(
        'Features: '
        'Stories, Reels, Posts, Videos, Bulk downloads'
    )

    print(
        'Server running on: '
        'http://localhost:5000'
    )

    print('=' * 60)

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )