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

# Render sets $PORT at runtime; default to 8000 for local/Docker Compose use.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT is expanded at container start (Render requires this).
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
