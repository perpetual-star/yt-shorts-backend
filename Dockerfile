# Use official Python base image
FROM python:3.11-slim

# Install ffmpeg and yt-dlp
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir yt-dlp fastapi uvicorn

# Set working directory
WORKDIR /app

# Copy requirements first and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
