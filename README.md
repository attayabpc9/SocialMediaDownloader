# 🌐 Universal Social Media Downloader

A powerful and flexible **Flask-based web application** that lets you download content from **YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit**, and more — all through an intuitive web interface or via APIs.

**Made with ❤️ by Soham Roy Chowdhury**

---

## 🚀 Key Features

### 🔄 Multi-Platform Download Support

* **YouTube**: Videos, Shorts, Playlists, Subtitles
* **Instagram**: Posts, Reels, Stories, IGTV, Carousels
* **TikTok**: High-quality video downloads with metadata
* **Twitter/X**: Videos, images, threads
* **Facebook**: Public videos and posts
* **Reddit**: Videos, images, and GIFs
* **Other**: Any media supported by `yt-dlp`

### ⚙️ Advanced Functionality

* **Automatic Platform Detection** via URL
* **Bulk Downloads**: Paste multiple URLs and download all at once
* **Best Available Quality** (up to 1080p)
* **Metadata & Subtitle Support**
* **Organized Storage**: Timestamped download folders
* **ZIP Downloads** for entire folders
* **Web UI + REST API**
* **File Browser** for managing downloads

---

## 📦 Installation

### ✅ Prerequisites

* Python 3.7+
* pip (Python package manager)

### 🔧 Install Dependencies

```bash
pip install flask requests yt-dlp instaloader werkzeug
```

Or with a `requirements.txt`:

```
Flask==2.3.3
requests==2.31.0
yt-dlp==2023.10.13
instaloader==4.10.3
Werkzeug==2.3.7
```

```bash
pip install -r requirements.txt
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

### `GET /downloads`

List all downloaded files

### `GET /download-file/<filename>`

Download a specific file

### `GET /download-folder/<foldername>`

Download a full folder as ZIP

### `POST /clear-downloads`

Delete all downloaded content

### `GET /supported-platforms`

List of supported platforms

---

## ⚙️ Configuration

### 🔐 Security

Before using in production, change the secret key:

```python
app.config['SECRET_KEY'] = 'your-super-secret-key'
```

### 📁 Download Directory

By default:

```python
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
```

Modify this path in the code if needed.

---

## 🧱 Project Structure

```
your-project/
├── app.py                # Main Flask app
├── templates/
│   └── index.html        # Frontend template
├── downloads/            # All downloaded media
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

### Twitter/X

* Threads, videos, images
* Preserves tweet metadata

### Facebook

* Downloads public videos and post media

### Reddit

* Supports all native Reddit media formats

---

## 🛠 Error Handling & Troubleshooting

* Clear errors for invalid or private URLs
* Logs platform-specific failures
* Bulk downloads continue despite individual errors

### Common Fixes

* `ModuleNotFoundError` → Run `pip install -r requirements.txt`
* Download failure → Check if the URL is public
* Write error → Ensure correct permissions
* Instagram issues → Try using login for private/stories

---

## 🧪 Debug / Production Mode

Run in debug (default):

```python
app.run(debug=True)
```

For production:

```python
app.run(debug=False, host='0.0.0.0', port=5000)
```

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
