# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2025-12-07 (EXPERIMENTAL)

### Added - Load Balancing (Experimental)
- **Load Balancing Mode**: New experimental feature to distribute bulk downloads across multiple sources
- Automatically detects when 10+ chapters (configurable) are queued for the same manga
- Distributes downloads across sources using round-robin strategy
- Proactively downloads from alternative sources to avoid rate limits
- Downloaded files are automatically copied to the original source location
- Smart activation - only engages for bulk download batches
- Configurable via environment variables:
  - `ENABLE_LOAD_BALANCING`: Enable/disable (default: false)
  - `MAX_LOAD_BALANCED_DOWNLOADS`: Max parallel downloads (default: 4)
  - `LOAD_BALANCE_THRESHOLD`: Min chapters to activate (default: 10)

### Technical Details
- Load balanced downloads run independently from fallback system
- Failed load balanced downloads fall through to normal Suwayomi error handling
- Completed downloads are copied to original source location and original queue entry is removed
- Round-robin source selection per manga to distribute load evenly
- Full logging support with dedicated emoji indicators (🔄 ⚖️ ✅)

### Warning
⚠️ **This is an experimental feature!** Use at your own risk. The load balancing system:
- May increase API calls to alternative sources
- Could trigger rate limits on some sources
- Is designed for bulk downloads, not single chapter downloads
- Should be tested in your environment before relying on it

Recommended to start with default settings and monitor behavior before adjusting.

---

## [1.1.3] - 2024-12-06

### Fixed
- **Critical**: Fixed parallel download conflicts where first completed chapter deleted entire manga folder
- **Critical**: Fixed infinite retry loops after successful recovery
- **Critical**: Fixed filename detection by querying Suwayomi database for expected filename
- `delete_alt_source_files()` now only deletes specific CBZ file instead of entire folder
- Added `pending_detection` tracking to prevent immediate retries after recovery
- Added timeout (2 min) for chapters stuck in ERROR state after recovery

### Changed
- `copy_and_rename_cbz()` now accepts chapter_id parameter
- `get_suwayomi_expected_filename()` queries database for exact filename with scanlator prefix
- Updated docker-compose.yml with clarifying comments about filename patterns

### Added
- GitHub issue templates (bug_report.yml, feature_request.yml)
- Better error handling for edge cases

---

## [1.1.2] - 2024-12-05

### Added
- Intelligent source retry tracking that remembers original source
- Configurable retry loops via `MAX_SOURCE_RETRY_LOOPS` environment variable
- Smart loop detection to prevent infinite retries

### Changed
- Script now tracks which sources have been tried for each failure
- After exhausting all sources, script will loop through them again (up to configured limit)
- Source priority list is respected in each retry loop

---

## [1.1.1] - 2024-12-04

### Fixed
- Fixed lambda capture bug in source filename pattern transforms
- Fixed version comparison logic in update checker
- Improved retry logic for download operations
- Better error handling in file operations

---

## [1.1.0] - 2024-12-03

### Added
- **Parallel Downloads**: Support for concurrent fallback downloads (default: 3)
- `MAX_CONCURRENT_FALLBACKS` environment variable to control parallelism
- Active download tracking and monitoring
- Download progress checking during parallel operations

### Changed
- Refactored main loop to support parallel fallback processing
- Improved download status monitoring
- Better handling of active downloads

---

## [1.0.0] - 2024-12-01

### Added
- Initial release
- Automatic fallback downloading from alternative sources
- Docker and Docker Compose support
- Configurable source priority
- Filename pattern matching per source
- GraphQL API integration with Suwayomi
- Automatic file ownership management (CHOWN_UID/GID)
- Update checker
- Comprehensive logging

### Features
- Monitors Suwayomi download queue for failures
- Searches alternative sources for failed chapters
- Automatically downloads and places files in correct location
- Title similarity matching
- Chapter number matching
- Configurable check interval
- Environment variable configuration
