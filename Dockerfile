FROM python:3.12-slim

WORKDIR /app

# Install Python deps first so this layer caches unless requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app ./app
COPY sim ./sim
COPY static ./static
COPY tests ./tests

EXPOSE 8000

# Default command runs the backend. The sensor service overrides this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
