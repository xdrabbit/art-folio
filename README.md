# ArtFolio

A simple, local-first web application to organize and version digital art.

## Tech Stack

- **Backend:** Flask (Python)
- **Frontend:** React (via CDN for simplicity)
- **Database:** SQLite
- **API:** REST

## Features

- **Groups:** Organize art into collections (e.g., "Sketches," "Client Work").
- **Items:** Represent a single piece of art within a group.
- **Versions:** Upload multiple revisions of an art item and view them chronologically.
- **File Storage:** Images are stored on the local filesystem.

## Quick Start

1.  **Install Dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the Application:**
    The first run will create the `artfolio.db` database and the `uploads` directory.
    ```bash
    python app.py
    ```

3.  **Access the App:**
    Open your browser and navigate to `http://127.0.0.1:5001`.

    ## Timelapse / Video export

    This app includes a local timelapse exporter that uses ffmpeg to stitch an item's versions into a short MP4 slideshow. It's privacy-friendly and runs locally.

    Requirements:
    - ffmpeg available on the machine (install via your package manager, e.g. `sudo apt install ffmpeg`)

    How to use:
    - Open an item with versions, then click "Create Timelapse (mp4)" — the server will run ffmpeg and save an MP4 next to the images. You can preview and download the file.

    If you'd prefer to open the exported images in a GUI editor like OpenShot, you can either import the exported MP4 into OpenShot or open the images directly in OpenShot and export a project there.

## API Endpoints

- `GET /api/health`: Health check.
- `POST /api/groups`: Create a new group.
- `GET /api/groups`: Get all groups.
- `GET /api/groups/<id>/items`: Get all items in a group.
- `POST /api/items`: Create a new item in a group.
- `POST /api/items/<id>/versions`: Upload a new version for an item.
- `GET /api/items/<id>/versions`: Get all versions for an item.
- `GET /media/<group_id>/<item_id>/<filename>`: Serve an image file.
