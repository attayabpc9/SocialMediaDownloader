# 🌐 Universal Social Media Downloader

A scalable Flask web service with a separate Render worker, PostgreSQL job queue and S3-compatible private file storage. Users do not need accounts.

**Made with ❤️ by Soham Roy Chowdhury**

---

## 🚀 Key Features

### 🔄 Multi-Platform Download Support

* **YouTube**: Videos, Shorts, Playlists, Subtitles
* **Instagram**: Posts, Reels, Stories, IGTV, Carousels
* **TikTok**: High-quality video downloads with metadata
* **Facebook**: Public videos and posts

### ⚙️ Advanced Functionality

* **Automatic Platform Detection** via URL
* **Bulk Downloads**: Paste multiple URLs and download all at once
* **Best Available Quality** (up to 1080p)
* **Metadata & Subtitle Support**
* **Web UI + REST API**
* **Separate worker processing** for scalable downloads
* **Anonymous temporary jobs** without user accounts

---

## 📦 Installation

### ✅ Prerequisites

* Python 3.9+
* pip (Python package manager)
* PostgreSQL for shared job records
* S3-compatible storage for finished files

### 🔧 Install Dependencies

```bash
pip install -r requirements.txt
```

The web service does not install or run media download tools. The separate worker service performs downloads and uploads finished files to S3-compatible storage.

The required packages are:

```
Flask==2.3.3
requests==2.31.0
Werkzeug==2.3.7
```

Configure the server before starting it:

```text
VIDZFLOW_SECRET_KEY=<long-random-secret>
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
S3_BUCKET=your-private-bucket
S3_ACCESS_KEY_ID=your-storage-access-key
S3_SECRET_ACCESS_KEY=your-storage-secret-key
```

---

## 💻 Usage

### ▶️ Run the Server

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

### 🌐 Web Interface

1. Paste any supported social media URL
2. Click download
3. Browse/download content directly from the interface

---

## 🔌 API Endpoints

### `POST /download`

Download a single URL:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### `POST /bulk-download`

Download multiple URLs:

```json
{
  "urls": [
    "https://youtube.com/...",
    "https://instagram.com/...",
    "https://tiktok.com/..."
  ]
}
```

### `GET /jobs/<job-token>`

Get the status and final file link for one anonymous job. The token is returned by `POST /download` and expires automatically.

### `GET /supported-platforms`

List of supported platforms

---

## ⚙️ Configuration

Copy `.env.example` to the environment settings for both Render services and replace every placeholder. Keep the database password, secret key and storage credentials private. Render must provide the same `DATABASE_URL` and `VIDZFLOW_SECRET_KEY` to the web and worker services.

Set `VIDZFLOW_SECRET_KEY` to exactly the same long random value in both services. The web service limits active queued/processing jobs with `MAX_ACTIVE_JOBS`; the worker limits each job with `WORKER_JOB_TIMEOUT_SECONDS`, `MAX_DOWNLOAD_SIZE` and `MAX_DOWNLOAD_BYTES`.

---

## 🧱 Project Structure

```
your-project/
├── app.py                # Lightweight Flask coordinator
├── config.py             # Environment configuration
├── database.py           # Shared database engine and sessions
├── models.py             # Shared job model
├── worker.py             # Render background worker
├── anonymous_jobs.py     # Expiring anonymous job tokens
├── url_validation.py     # URL and platform validation
├── .env.example         # Safe configuration template
├── templates/
│   ├── index.html        # Frontend template
│   ├── privacy.html      # Privacy page
│   └── terms.html        # Terms page
├── requirements.txt      # Server dependencies
└── README.md             # You're reading it
```

---

## 📱 Platform-Specific Highlights

### YouTube

* Supports videos, playlists, shorts
* English subtitle download
* Best quality + uploader/title metadata

### Instagram

* Posts, reels, carousels, stories, IGTV
* Requires login for private/stories

### TikTok

* High-resolution videos
* Saves captions and author info

### Facebook

* Downloads public videos and post media

---

## 🛠 Error Handling & Troubleshooting

* Clear errors for invalid or private URLs
* Logs platform-specific failures
* Bulk downloads continue despite individual errors

### Common Fixes

* `ModuleNotFoundError` → Run `pip install -r requirements.txt`
* Download failure → Check if the URL is public
* Storage error → Check the S3 bucket credentials and permissions

### Render deployment

Deploy `render.yaml` as a Blueprint. It creates a web service and a separate background worker. Both services must use the same PostgreSQL database and `VIDZFLOW_SECRET_KEY`. Configure the S3-compatible storage credentials on the worker.

SQLite is only the local-development fallback. Do not use SQLite for the Render deployment because Render instances can restart and multiple services cannot safely share a local SQLite file. The PostgreSQL plan and S3-compatible storage may have a cost; confirm current Render and storage pricing before deploying.

---

## 🧪 Production mode

Render starts the web service with Gunicorn through the Docker configuration. The application runs with debug mode disabled. For local development, use `python app.py` and a local SQLite database.

---

## 📜 License

This project is licensed under the **MIT License**. See `LICENSE` for details.

---

## ⚠️ Legal & Ethical Use

This tool is intended strictly for **personal and educational** purposes.
Please make sure you:

* Follow platform terms of service
* Do **not** download private or copyrighted material
* Use responsibly and ethically

---

**Made with ❤️ by Soham Roy Chowdhury**
