FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching optimization)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]