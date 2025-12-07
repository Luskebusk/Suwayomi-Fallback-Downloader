#!/usr/bin/env python3
"""
Suwayomi Fallback Downloader
Monitors download queue for failures and attempts to download from alternative sources.
"""

__version__ = "1.1.0"

import os
import shutil
import time
import logging
import re
from difflib import SequenceMatcher
import requests

# ============================================================================
# CONFIGURATION - Edit these settings to match your setup
# ============================================================================

# Connection Settings
SUWAYOMI_URL = os.environ.get("SUWAYOMI_URL", "http://localhost:4567/api/graphql")
USERNAME = os.environ.get("SUWAYOMI_USER", "username")
PASSWORD = os.environ.get("SUWAYOMI_PASS", "password")

# File System Settings
DOWNLOADS_PATH = os.environ.get("DOWNLOADS_PATH", "/downloads/mangas")
CHOWN_UID = int(os.environ.get("CHOWN_UID", "1000"))  # User ID for file ownership
CHOWN_GID = int(os.environ.get("CHOWN_GID", "1000"))  # Group ID for file ownership

# Source Priority
# List of source IDs to try in order (most reliable first).
# The script will attempt each source until a successful download is found.
# To find source IDs: Check your Suwayomi source list or browser dev tools.
SOURCE_PRIORITY = [
    "2499283573021220255",   # MangaDex (EN)
    "6247824327199706550",   # Asura Scans (EN)
    "2528986671771677900",   # Mangakakalot (EN)
    "4215511432986138970",   # Mangabat (EN)
    "2",                     # Mangahere (EN)
    "6084907896154116083",   # MangaFire (EN)
    "7890050626002177109",   # Bato.to (EN)
    "4972933717624256217",   # Comick (EN)
]

# Filename Patterns per Source
# Define how each source names its downloaded files.
# Format: "source_id": {"prefix": "text_", "transform": function}
# - prefix: Text added before the chapter name
# - transform: Function to modify the chapter name (e.g., replace characters)
#
# Example: If a source prefixes files with "www.example.com_" and replaces colons,
# add: "source_id": {"prefix": "www.example.com_", "transform": lambda name: name.replace(":", "_")}
SOURCE_FILENAME_PATTERNS = {
    "4215511432986138970": {  # Mangabat
        "prefix": "www.mangabats.com_",
        "transform": lambda name: name,
    },
    "6084907896154116083": {  # MangaFire
        "prefix": "",
        "transform": lambda name: name.replace(":", "_"),
    },
    "2528986671771677900": {  # Mangakakalot
        "prefix": "www.mangakakalot.gg_",
        "transform": lambda name: name,
    },
}

# Monitoring Settings
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))  # How often to check for failed downloads (seconds)
TITLE_MATCH_THRESHOLD = 0.85  # Minimum similarity score (0-1) to match manga titles
DOWNLOAD_WAIT_TIMEOUT = 300  # Maximum time to wait for a download to complete (seconds)
DOWNLOAD_CHECK_INTERVAL = 5  # How often to check download progress (seconds)
MAX_CONCURRENT_FALLBACKS = int(os.environ.get("MAX_CONCURRENT_FALLBACKS", "3"))  # Max parallel fallback downloads

# ============================================================================
# END CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cache for source names and reverse lookup
_source_name_cache = {}
_source_id_by_name_cache = {}

# Active fallback downloads tracking
# Format: {chapter_id: {"source_id": str, "manga_title": str, "chapter_name": str, "start_time": float, "dest_source_id": str}}
_active_fallback_downloads = {}


def check_for_updates() -> None:
    """Check if a newer version is available on GitHub."""
    try:
        response = requests.get(
            "https://api.github.com/repos/Luskebusk/Suwayomi-Fallback-Downloader/releases/latest",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")
            current_version = __version__
            
            if latest_version and latest_version != current_version:
                logger.warning("=" * 60)
                logger.warning(f"UPDATE AVAILABLE: v{latest_version} (current: v{current_version})")
                logger.warning(f"Download: {data.get('html_url', 'https://github.com/Luskebusk/Suwayomi-Fallback-Downloader/releases')}")
                logger.warning("=" * 60)
            else:
                logger.info(f"Running latest version: v{current_version}")
    except Exception as e:
        logger.debug(f"Could not check for updates: {e}")


def graphql_request(query: str, variables: dict = None) -> dict:
    """Make a GraphQL request to Suwayomi."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        SUWAYOMI_URL,
        json=payload,
        auth=(USERNAME, PASSWORD),
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_source_name(source_id: str) -> str:
    """Get source name by ID (cached)."""
    if source_id in _source_name_cache:
        return _source_name_cache[source_id]

    query = """
    query GET_SOURCE($id: LongString!) {
        source(id: $id) {
            id
            displayName
        }
    }
    """
    try:
        result = graphql_request(query, {"id": source_id})
        name = result.get("data", {}).get("source", {}).get("displayName", f"Unknown ({source_id})")
        _source_name_cache[source_id] = name
        _source_id_by_name_cache[name] = source_id
        return name
    except Exception:
        return f"Unknown ({source_id})"


def get_source_id_by_name(display_name: str) -> str | None:
    """Reverse lookup: display name -> source id."""
    if display_name in _source_id_by_name_cache:
        return _source_id_by_name_cache[display_name]
    # As a fallback, try fetching all sources via extensions listing
    query = """
    query {
      extensions {
        nodes {
          id
          displayName
        }
      }
    }
    """
    try:
        res = graphql_request(query)
        nodes = res.get("data", {}).get("extensions", {}).get("nodes", [])
        for node in nodes:
            _source_name_cache[node["id"]] = node["displayName"]
            _source_id_by_name_cache[node["displayName"]] = node["id"]
        return _source_id_by_name_cache.get(display_name)
    except Exception:
        return None


def get_source_folder(source_id: str) -> str:
    """Get the folder name for a source."""
    return get_source_name(source_id)


def get_filename_for_source(source_id: str, chapter_name: str) -> str:
    """Generate the correct filename for a chapter based on source."""
    pattern = SOURCE_FILENAME_PATTERNS.get(source_id, {"prefix": "", "transform": lambda x: x})
    prefix = pattern["prefix"]
    transformed_name = pattern["transform"](chapter_name)
    return f"{prefix}{transformed_name}.cbz"


def get_failed_downloads() -> list:
    """Get all downloads in ERROR state."""
    query = """
    {
        downloadStatus {
            queue {
                manga { id title sourceId }
                chapter { id name chapterNumber }
                state
                tries
            }
        }
    }
    """
    result = graphql_request(query)
    queue = result.get("data", {}).get("downloadStatus", {}).get("queue", [])
    return [item for item in queue if item["state"] == "ERROR"]


def get_download_status() -> list:
    """Get current download queue."""
    query = """
    {
        downloadStatus {
            queue {
                chapter { id }
                state
                progress
            }
        }
    }
    """
    result = graphql_request(query)
    return result.get("data", {}).get("downloadStatus", {}).get("queue", [])


def search_manga_on_source(title: str, source_id: str) -> list:
    """Search for a manga on a specific source."""
    query = """
    mutation FETCH_SOURCE_MANGA($input: FetchSourceMangaInput!) {
        fetchSourceManga(input: $input) {
            hasNextPage
            mangas {
                id
                title
                inLibrary
                sourceId
            }
        }
    }
    """
    variables = {
        "input": {
            "type": "SEARCH",
            "source": source_id,
            "query": title,
            "page": 1
        }
    }

    try:
        result = graphql_request(query, variables)
        return result.get("data", {}).get("fetchSourceManga", {}).get("mangas", [])
    except Exception as e:
        logger.warning(f"Search failed on source {source_id}: {e}")
        return []


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles."""
    def normalize(t):
        t = t.lower().strip()
        t = re.sub(r'[^\w\s]', '', t)
        return t

    return SequenceMatcher(None, normalize(title1), normalize(title2)).ratio()


def find_best_match(original_title: str, search_results: list) -> dict:
    """Find the best matching manga from search results."""
    best_match = None
    best_score = 0

    for manga in search_results:
        score = title_similarity(original_title, manga["title"])
        if score > best_score and score >= TITLE_MATCH_THRESHOLD:
            best_score = score
            best_match = manga
            best_match["_match_score"] = score

    return best_match


def fetch_chapters(manga_id: int) -> list:
    """Fetch chapters for a manga."""
    query = """
    mutation FETCH_CHAPTERS($input: FetchChaptersInput!) {
        fetchChapters(input: $input) {
            chapters {
                id
                name
                chapterNumber
                mangaId
              }
        }
    }
    """
    variables = {"input": {"mangaId": manga_id}}

    try:
        result = graphql_request(query, variables)
        return result.get("data", {}).get("fetchChapters", {}).get("chapters", [])
    except Exception as e:
        logger.warning(f"Failed to fetch chapters for manga {manga_id}: {e}")
        return []


def find_matching_chapter(chapters: list, target_chapter_num: float) -> dict | None:
    """Find a chapter matching the target chapter number."""
    for chapter in chapters:
        if abs(chapter["chapterNumber"] - target_chapter_num) < 0.01:
            return chapter
    return None


def enqueue_download(chapter_id: int) -> bool:
    """Add a chapter to the download queue."""
    query = """
    mutation ENQUEUE_CHAPTER_DOWNLOADS($input: EnqueueChapterDownloadsInput!) {
        enqueueChapterDownloads(input: $input) {
            downloadStatus { state }
        }
    }
    """
    variables = {"input": {"ids": [chapter_id]}}

    try:
        graphql_request(query, variables)
        return True
    except Exception as e:
        logger.error(f"Failed to enqueue chapter {chapter_id}: {e}")
        return False


def start_download(chapter_id: int) -> bool:
    """Start downloading a chapter immediately (for parallel downloads)."""
    query = """
    mutation START_DOWNLOADS($input: StartDownloadsInput!) {
        startDownloads(input: $input) {
            downloadStatus { state }
        }
    }
    """
    variables = {"input": {"clientMutationId": str(chapter_id)}}

    try:
        # First enqueue, then start
        if enqueue_download(chapter_id):
            # Give a moment for enqueue to register
            time.sleep(0.5)
            try:
                graphql_request(query, variables)
            except Exception:
                # START_DOWNLOADS might not exist in all versions, fallback to just enqueue
                pass
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to start download for chapter {chapter_id}: {e}")
        return False


def dequeue_download(chapter_id: int) -> bool:
    """Remove a chapter from the download queue."""
    query = """
    mutation DEQUEUE_CHAPTER_DOWNLOAD($input: DequeueChapterDownloadInput!) {
        dequeueChapterDownload(input: $input) {
            downloadStatus { state }
        }
    }
    """
    variables = {"input": {"id": chapter_id}}

    try:
        graphql_request(query, variables)
        logger.info(f"    Dequeued chapter {chapter_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to dequeue chapter {chapter_id}: {e}")
        return False


def enqueue_to_mark_downloaded(chapter_id: int) -> bool:
    """Re-enqueue original chapter to trigger Suwayomi to detect the file exists."""
    query = """
    mutation ENQUEUE_CHAPTER_DOWNLOADS($input: EnqueueChapterDownloadsInput!) {
        enqueueChapterDownloads(input: $input) {
            downloadStatus { state }
        }
    }
    """
    variables = {"input": {"ids": [chapter_id]}}

    try:
        graphql_request(query, variables)
        logger.info(f"    Re-enqueued chapter {chapter_id} to mark as downloaded")
        return True
    except Exception as e:
        logger.warning(f"Failed to re-enqueue chapter {chapter_id}: {e}")
        return False


def delete_downloaded_chapter(chapter_id: int) -> bool:
    """Delete downloaded chapter files via API."""
    query = """
    mutation DELETE_DOWNLOADED_CHAPTER($input: DeleteDownloadedChapterInput!) {
        deleteDownloadedChapter(input: $input) {
            chapters { id isDownloaded }
        }
    }
    """
    variables = {"input": {"id": chapter_id}}

    try:
        graphql_request(query, variables)
        return True
    except Exception as e:
        logger.warning(f"Failed to delete chapter {chapter_id}: {e}")
        return False


def wait_for_download(chapter_id: int, timeout: int = DOWNLOAD_WAIT_TIMEOUT) -> bool:
    """Wait for a chapter download to complete."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        queue = get_download_status()

        chapter_status = None
        for item in queue:
            if item["chapter"]["id"] == chapter_id:
                chapter_status = item
                break

        # If not present in queue anymore, assume finished
        if chapter_status is None:
            time.sleep(2)
            return True

        if chapter_status["state"] == "FINISHED":
            return True
        elif chapter_status["state"] == "ERROR":
            return False

        progress = chapter_status.get("progress", 0)
        logger.info(f"    Download progress: {progress}%")
        time.sleep(DOWNLOAD_CHECK_INTERVAL)

    logger.warning(f"    Download timeout after {timeout}s")
    return False


def check_active_downloads() -> dict:
    """Check status of all active fallback downloads and return completed ones."""
    if not _active_fallback_downloads:
        return {}

    queue = get_download_status()
    queue_by_id = {item["chapter"]["id"]: item for item in queue}
    
    completed = {}
    timed_out = []
    current_time = time.time()

    for chapter_id, info in list(_active_fallback_downloads.items()):
        # Check for timeout
        if current_time - info["start_time"] > DOWNLOAD_WAIT_TIMEOUT:
            logger.warning(f"    Fallback download timeout for chapter {chapter_id}")
            timed_out.append(chapter_id)
            continue

        # Check status in queue
        status = queue_by_id.get(chapter_id)
        
        if status is None:
            # Not in queue anymore - completed
            completed[chapter_id] = info
        elif status["state"] == "FINISHED":
            completed[chapter_id] = info
        elif status["state"] == "ERROR":
            logger.warning(f"    Fallback download failed for chapter {chapter_id}")
            timed_out.append(chapter_id)

    # Clean up completed and failed
    for chapter_id in completed:
        del _active_fallback_downloads[chapter_id]
    for chapter_id in timed_out:
        if chapter_id in _active_fallback_downloads:
            del _active_fallback_downloads[chapter_id]

    return completed


def list_existing_manga_folders(manga_title: str) -> list[tuple[str, str, int]]:
    """
    Scan DOWNLOADS_PATH and return a list of tuples:
    (source_folder_name, full_manga_path, cbz_count) for folders matching manga_title.
    """
    matches = []
    if not os.path.exists(DOWNLOADS_PATH):
        return matches

    for source_folder in os.listdir(DOWNLOADS_PATH):
        source_path = os.path.join(DOWNLOADS_PATH, source_folder)
        if not os.path.isdir(source_path):
            continue
        # look for exact or similar title folder
        for folder in os.listdir(source_path):
            folder_path = os.path.join(source_path, folder)
            if not os.path.isdir(folder_path):
                continue
            if title_similarity(folder, manga_title) >= TITLE_MATCH_THRESHOLD:
                cbz_count = len([f for f in os.listdir(folder_path) if f.lower().endswith(".cbz")])
                matches.append((source_folder, folder_path, cbz_count))
    return matches


def resolve_destination_source_id(manga_title: str, default_source_id: str) -> str:
    """
    Decide which sourceId folder we should write to:
    - Prefer the source folder that already contains the manga with most files.
    - Otherwise, fall back to the default_source_id (from the failed item).
    """
    existing = list_existing_manga_folders(manga_title)
    if existing:
        # pick the folder with the highest cbz_count
        existing.sort(key=lambda x: x[2], reverse=True)
        chosen_source_folder = existing[0][0]  # displayName like "Mangakakalot (EN)"
        chosen_id = get_source_id_by_name(chosen_source_folder)
        if chosen_id:
            logger.info(f"    Destination resolved to existing source folder: {chosen_source_folder}")
            return chosen_id
        else:
            logger.info(f"    Existing folder found but could not resolve source id: {chosen_source_folder}. Using default.")
    return default_source_id


def find_cbz_file(source_id: str, manga_title: str, chapter_name: str) -> str | None:
    """Find the downloaded CBZ file."""
    source_folder = get_source_folder(source_id)
    manga_path = os.path.join(DOWNLOADS_PATH, source_folder, manga_title)

    if not os.path.exists(manga_path):
        source_path = os.path.join(DOWNLOADS_PATH, source_folder)
        if os.path.exists(source_path):
            for folder in os.listdir(source_path):
                if title_similarity(folder, manga_title) >= TITLE_MATCH_THRESHOLD:
                    manga_path = os.path.join(source_path, folder)
                    break

    if not os.path.exists(manga_path):
        logger.warning(f"    Manga folder not found: {manga_path}")
        return None

    # Try filename contains chapter_name
    for filename in os.listdir(manga_path):
        if filename.lower().endswith('.cbz'):
            if chapter_name in filename or chapter_name.replace(" ", "") in filename:
                return os.path.join(manga_path, filename)

    # Fallback: match by chapter number
    chapter_num_match = re.search(r'(\d+(?:\.\d+)?)', chapter_name)
    if chapter_num_match:
        chapter_num = chapter_num_match.group(1)
        for filename in os.listdir(manga_path):
            if filename.lower().endswith('.cbz') and chapter_num in filename:
                return os.path.join(manga_path, filename)

    return None


def copy_and_rename_cbz(source_file: str, dest_source_id: str, manga_title: str, chapter_name: str) -> bool:
    """Copy CBZ file to original source folder with correct naming."""
    dest_source_folder = get_source_folder(dest_source_id)
    dest_manga_path = os.path.join(DOWNLOADS_PATH, dest_source_folder, manga_title)
    dest_filename = get_filename_for_source(dest_source_id, chapter_name)
    dest_path = os.path.join(dest_manga_path, dest_filename)

    try:
        os.makedirs(dest_manga_path, exist_ok=True)
        shutil.copy2(source_file, dest_path)
        # Normalize ownership to avoid mixed root/1000
        try:
            os.chown(dest_path, CHOWN_UID, CHOWN_GID)
        except Exception as e:
            logger.warning(f"    Could not chown {dest_path} to {CHOWN_UID}:{CHOWN_GID}: {e}")
        logger.info(f"    Copied to: {dest_path}")
        return True
    except Exception as e:
        logger.error(f"    Failed to copy file: {e}")
        return False


def delete_alt_source_files(source_id: str, manga_title: str) -> bool:
    """Delete the alt source manga folder to save space."""
    source_folder = get_source_folder(source_id)
    manga_path = os.path.join(DOWNLOADS_PATH, source_folder, manga_title)

    try:
        if os.path.exists(manga_path):
            shutil.rmtree(manga_path)
            logger.info(f"    Deleted alt source folder: {manga_path}")

            source_path = os.path.join(DOWNLOADS_PATH, source_folder)
            if os.path.exists(source_path) and not os.listdir(source_path):
                os.rmdir(source_path)

        return True
    except Exception as e:
        logger.warning(f"    Failed to delete alt source folder: {e}")
        return False


def start_fallback_download(failed_item: dict) -> bool:
    """Start a fallback download for a failed chapter (non-blocking)."""
    manga_title = failed_item["manga"]["title"]
    failed_source_id = failed_item["manga"]["sourceId"]
    chapter_num = failed_item["chapter"]["chapterNumber"]
    chapter_name = failed_item["chapter"]["name"]
    failed_chapter_id = failed_item["chapter"]["id"]

    failed_source_name = get_source_name(failed_source_id)

    logger.info(f"Processing failed download: {manga_title} - {chapter_name}")
    logger.info(f"  Original source (from queue): {failed_source_name}")

    # Resolve the true destination source by scanning existing folders
    dest_source_id = resolve_destination_source_id(manga_title, failed_source_id)
    dest_source_name = get_source_name(dest_source_id)
    if dest_source_id != failed_source_id:
        logger.info(f"  Overriding destination to existing source: {dest_source_name}")

    for source_id in SOURCE_PRIORITY:
        # Skip the destination source when searching alt sources
        if source_id == dest_source_id:
            continue

        source_name = get_source_name(source_id)
        logger.info(f"  Trying source: {source_name}")

        search_results = search_manga_on_source(manga_title, source_id)
        if not search_results:
            logger.info(f"    No results found")
            continue

        match = find_best_match(manga_title, search_results)
        if not match:
            logger.info(f"    No matching title found")
            continue

        logger.info(f"    Found match: {match['title']} (score: {match.get('_match_score', 0):.2f})")

        chapters = fetch_chapters(match["id"])
        if not chapters:
            logger.info(f"    No chapters found")
            continue

        target_chapter = find_matching_chapter(chapters, chapter_num)
        if not target_chapter:
            logger.info(f"    Chapter {chapter_num} not found")
            continue

        logger.info(f"    Found chapter: {target_chapter['name']} (ID: {target_chapter['id']})")

        # Start the download (non-blocking)
        if not start_download(target_chapter["id"]):
            continue

        # Track this download
        _active_fallback_downloads[target_chapter["id"]] = {
            "source_id": source_id,
            "manga_title": match["title"],
            "chapter_name": target_chapter["name"],
            "start_time": time.time(),
            "dest_source_id": dest_source_id,
            "original_manga_title": manga_title,
            "original_chapter_name": chapter_name,
            "failed_chapter_id": failed_chapter_id,
        }

        logger.info(f"    Download started from {source_name} (parallel mode)")
        return True

    logger.warning(f"  ✗ Could not find alternative source for {manga_title} - {chapter_name}")
    return False


def finalize_fallback_download(chapter_id: int, info: dict) -> bool:
    """Finalize a completed fallback download by moving files and updating Suwayomi."""
    source_id = info["source_id"]
    manga_title = info["manga_title"]
    chapter_name = info["chapter_name"]
    dest_source_id = info["dest_source_id"]
    original_manga_title = info["original_manga_title"]
    original_chapter_name = info["original_chapter_name"]
    failed_chapter_id = info["failed_chapter_id"]

    source_name = get_source_name(source_id)
    dest_source_name = get_source_name(dest_source_id)

    logger.info(f"Finalizing fallback download: {original_manga_title} - {original_chapter_name}")

    # Give filesystem a moment to finalize
    time.sleep(2)

    cbz_file = find_cbz_file(source_id, manga_title, chapter_name)

    if not cbz_file:
        logger.warning(f"    Could not find downloaded CBZ file from {source_name}")
        return False

    logger.info(f"    Found CBZ: {cbz_file}")

    # Copy into resolved destination source (canonical folder)
    if not copy_and_rename_cbz(cbz_file, dest_source_id, original_manga_title, original_chapter_name):
        return False

    # Clean up alt source files
    delete_alt_source_files(source_id, manga_title)
    delete_downloaded_chapter(chapter_id)

    # Dequeue the failed download and re-enqueue original so Suwayomi marks it downloaded
    dequeue_download(failed_chapter_id)
    time.sleep(1)
    enqueue_to_mark_downloaded(failed_chapter_id)

    logger.info(f"  ✓ Successfully recovered {original_chapter_name} into {dest_source_name}")
    return True


def main():
    """Main loop - monitor and process failed downloads with parallel support."""
    logger.info("=" * 60)
    logger.info(f"Suwayomi Fallback Downloader v{__version__}")
    logger.info("=" * 60)
    logger.info(f"Suwayomi URL: {SUWAYOMI_URL}")
    logger.info(f"Downloads path: {DOWNLOADS_PATH}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info(f"Max concurrent fallbacks: {MAX_CONCURRENT_FALLBACKS}")
    logger.info("=" * 60)
    
    # Check for updates on startup
    check_for_updates()

    processed_failures = set()

    while True:
        try:
            # Check and finalize any completed fallback downloads
            completed = check_active_downloads()
            for chapter_id, info in completed.items():
                try:
                    finalize_fallback_download(chapter_id, info)
                except Exception as e:
                    logger.error(f"Error finalizing download for chapter {chapter_id}: {e}")
                    import traceback
                    traceback.print_exc()

            # Check for new failures and start fallback downloads if under limit
            if len(_active_fallback_downloads) < MAX_CONCURRENT_FALLBACKS:
                failed_downloads = get_failed_downloads()

                if failed_downloads:
                    new_failures = [
                        item for item in failed_downloads
                        if f"{item['manga']['id']}_{item['chapter']['id']}" not in processed_failures
                    ]

                    if new_failures:
                        # Start fallback downloads up to the concurrent limit
                        available_slots = MAX_CONCURRENT_FALLBACKS - len(_active_fallback_downloads)
                        to_process = new_failures[:available_slots]

                        if to_process:
                            logger.info(f"Found {len(new_failures)} new failed downloads, starting {len(to_process)}")

                            for item in to_process:
                                failure_key = f"{item['manga']['id']}_{item['chapter']['id']}"
                                try:
                                    start_fallback_download(item)
                                    processed_failures.add(failure_key)
                                    time.sleep(2)  # Small delay between starts
                                except Exception as e:
                                    logger.error(f"Error starting fallback for {item['manga']['title']}: {e}")
                                    import traceback
                                    traceback.print_exc()
            else:
                logger.info(f"Max concurrent fallbacks reached ({len(_active_fallback_downloads)}/{MAX_CONCURRENT_FALLBACKS}), waiting...")

            # Periodic cleanup
            if len(processed_failures) > 1000:
                processed_failures.clear()

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()