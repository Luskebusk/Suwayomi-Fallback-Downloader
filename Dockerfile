FROM python:3.11-slim

WORKDIR /app

# Install required Python packages
RUN pip install --no-cache-dir requests

# Copy the script
COPY suwayomi_fallback_downloader.py .

# Make script executable
RUN chmod +x suwayomi_fallback_downloader.py

# Run the script
CMD ["python", "-u", "suwayomi_fallback_downloader.py"]
