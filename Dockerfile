# Use a slim Python base image
FROM python:3.12-slim

# Install system dependencies (ffmpeg, curl, etc.)
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install yt-dlp explicitly (in case it's not in requirements.txt)
RUN pip install --no-cache-dir yt-dlp

# Copy the rest of the app
COPY . .

# Expose Railway’s dynamic port
EXPOSE 8080

# Run FastAPI with uvicorn on Railway's port
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

