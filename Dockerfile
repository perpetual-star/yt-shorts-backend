# Use a slim Python base image
FROM python:3.12-slim

# Install ffmpeg and dependencies
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose Railway's dynamic port
EXPOSE 8080

# Run FastAPI with uvicorn on Railway's port
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

