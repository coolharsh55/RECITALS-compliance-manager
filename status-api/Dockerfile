# Status API image
FROM python:3.12-slim

WORKDIR /app

# Install the pinned dependencies first so code changes reuse this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Serve the FastAPI app on port 8000 inside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
