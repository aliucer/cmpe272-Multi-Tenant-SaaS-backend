# Dockerfile (for development)
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for FastAPI
EXPOSE 8000

# Default command (use reload for hot updates)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "reload", "--reload-dir", "app"]
