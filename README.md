# Suwayomi Fallback Downloader

Automatically recover failed manga chapter downloads in Suwayomi by trying alternative sources.

> **Note:** This script is designed specifically for CBZ format downloads. It only handles `.cbz` files.

## Features

- **Automatic Recovery** - Detects and recovers failed downloads without manual intervention
- **Parallel Downloads** - Downloads from multiple sources simultaneously (up to 3 by default)
- **Smart Matching** - Finds the correct manga even with title variations
- **Source Priority** - Configure which sources to try first
- **File Organization** - Maintains your existing folder structure
- **Docker Ready** - Easy deployment with docker-compose
- **Fully Configurable** - All settings via environment variables

## Quick Links

📚 **[Full Documentation (Wiki)](../../wiki)** - Comprehensive guides and configuration

- [Quick Start Guide](../../wiki/Quick-Start) - Get up and running in 5 minutes
- [Configuration Guide](../../wiki/Configuration-Guide) - Customize sources and settings
- [Networking Setup](../../wiki/Networking-Setup) - Connect to your Suwayomi instance
- [Troubleshooting](../../wiki/Troubleshooting) - Common issues and solutions
- [Advanced Configuration](../../wiki/Advanced-Configuration) - Custom sources and performance tuning

## Quick Start

1. **Clone and navigate:**
   ```bash
   git clone https://github.com/Luskebusk/Suwayomi-Fallback-Downloader.git
   cd Suwayomi-Fallback-Downloader
   ```

2. **Configure `docker-compose.yml`:**
   - Set `SUWAYOMI_URL`, `SUWAYOMI_USER`, `SUWAYOMI_PASS`
   - Update volume path to match your Suwayomi downloads
   - Set `CHOWN_UID` and `CHOWN_GID` to your user/group IDs

3. **Start the container:**
   ```bash
   docker-compose up -d
   ```

4. **Verify:**
   ```bash
   docker-compose logs -f
   ```

**For detailed installation instructions, see the [Quick Start Guide](../../wiki/Quick-Start).**

## Configuration

All settings are configured via environment variables in `docker-compose.yml`. The script includes sensible defaults for most settings.

**Key configuration options:**
- Connection settings (URL, authentication)
- File system paths and permissions
- Source priority (8 default sources included)
- Parallel download limits
- Custom filename patterns

**For complete configuration documentation, see the [Configuration Guide](../../wiki/Configuration-Guide).**

## Common Issues

- **Connection problems?** See [Networking Setup](../../wiki/Networking-Setup)
- **Permission errors?** Check `CHOWN_UID` and `CHOWN_GID` in [Quick Start](../../wiki/Quick-Start)
- **Files not found?** Verify volume mounts match Suwayomi's paths
- **More issues?** Check the [Troubleshooting Guide](../../wiki/Troubleshooting)

## License

MIT License - See [LICENSE](LICENSE) file for details.## About

This was made mostly for personal use to solve persistent download failures due to rate limiting and source instability. Made in collaboration with AI.

Tested and working on Suwayomi build: **v2.1.2019**

**Current Version:** v1.1.0 (includes parallel download support)

## License

MIT License - See [LICENSE](LICENSE) file for details.