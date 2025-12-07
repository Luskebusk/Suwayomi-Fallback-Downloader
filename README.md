# Suwayomi Fallback Downloader

Automatically recover failed manga chapter downloads in Suwayomi by trying alternative sources.

> **Note:** This script is designed specifically for CBZ format downloads. It only handles `.cbz` files.

## How It Works

This script monitors your Suwayomi download queue for failed downloads. When a chapter fails to download from its primary source, the script:

1. **Detects** the failed download in the queue
2. **Searches** for the same manga on alternative sources (in priority order)
3. **Downloads** the chapter from the first available alternative source
4. **Moves & Renames** the file to match your primary source's naming convention
5. **Updates** Suwayomi to mark the chapter as downloaded

This ensures seamless integration - all your manga chapters stay organized under their original source, even when downloaded from alternatives.

## Comments

This was made mostly for personal use - I'm not aware of a better solution to this issue.
I was frustrated by downloads failing due to rate limiting or source problems.
Sharing in case anyone else has the same issue.
Made in collaboration with AI.

Tested and working on Suwayomi build: **v2.1.2019**

## Installation

### Prerequisites

- Docker and Docker Compose installed
- Suwayomi server running (either in Docker or standalone)
- Access to Suwayomi's download folder

### Quick Start

1. **Clone this repository:**
   ```bash
   git clone https://github.com/yourusername/Suwayomi-Fallback-Downloader.git
   cd Suwayomi-Fallback-Downloader
   ```

2. **Edit `docker-compose.yml`:**
   
   Update the following settings:
   
   ```yaml
   environment:
     SUWAYOMI_URL: "http://suwayomi:4567/api/graphql"  # Your Suwayomi URL
     SUWAYOMI_USER: "username"  # Your Suwayomi username
     SUWAYOMI_PASS: "password"  # Your Suwayomi password
   
   volumes:
     - /path/to/your/suwayomi/downloads:/downloads/mangas  # Same path as Suwayomi
   ```

3. **Find your User/Group IDs** (for proper file permissions):
   ```bash
   id -u  # Your user ID
   id -g  # Your group ID
   ```
   
   Update `CHOWN_UID` and `CHOWN_GID` in `docker-compose.yml` with these values.

4. **Start the container:**
   ```bash
   docker-compose up -d
   ```

5. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUWAYOMI_URL` | `http://localhost:4567/api/graphql` | Suwayomi GraphQL API endpoint |
| `SUWAYOMI_USER` | `username` | Suwayomi username (if auth enabled) |
| `SUWAYOMI_PASS` | `password` | Suwayomi password (if auth enabled) |
| `DOWNLOADS_PATH` | `/downloads/mangas` | Path to manga downloads folder |
| `CHOWN_UID` | `1000` | User ID for file ownership |
| `CHOWN_GID` | `1000` | Group ID for file ownership |
| `CHECK_INTERVAL` | `60` | Seconds between queue checks |

### Adding Custom Sources

Edit `suwayomi_fallback_downloader.py` to add or reorder sources:

1. **Add to Source Priority** (line ~35):
   ```python
   SOURCE_PRIORITY = [
       "2499283573021220255",   # MangaDex (EN)
       "YOUR_SOURCE_ID_HERE",   # Your Custom Source
       # ... other sources
   ]
   ```

2. **Add Filename Pattern** (if needed, line ~50):
   ```python
   SOURCE_FILENAME_PATTERNS = {
       "YOUR_SOURCE_ID_HERE": {
           "prefix": "www.example.com_",  # Prefix for filenames
           "transform": lambda name: name.replace(":", "_"),  # Name transformations
       },
   }
   ```

**Finding Source IDs:**
- Open Suwayomi in your browser
- Open Developer Tools (F12)
- Navigate to a source
- Check the Network tab for GraphQL requests containing the source ID

## Networking

### If Suwayomi is in Docker:

Add both containers to the same network:

```yaml
networks:
  - suwayomi_network

networks:
  suwayomi_network:
    external: true
```

Or use the container name directly in `SUWAYOMI_URL` (e.g., `http://suwayomi:4567/api/graphql`).

### If Suwayomi is on Host:

Use `http://host.docker.internal:4567/api/graphql` (Docker Desktop) or your host's IP address.

## Troubleshooting

**Downloads not being detected:**
- Ensure the Suwayomi URL is correct and accessible from the container
- Verify authentication credentials if enabled
- Check that the downloads path matches Suwayomi's configuration

**File permission issues:**
- Make sure `CHOWN_UID` and `CHOWN_GID` match your host user
- Verify the volume mount has proper read/write permissions

**No alternative sources found:**
- Check that your manga exists on the configured sources
- Adjust `TITLE_MATCH_THRESHOLD` if titles don't match exactly (default: 0.85)

## License

MIT License - See [LICENSE](LICENSE) file for details.