# Stage 1: build the React front end into plain static files.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python server, which also serves the files built above.
FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY data/ /srv/data/
COPY --from=web /web/dist /srv/static

# DATA_DIR:   the supplied reference files and manifest (read only)
# DB_PATH:    the SQLite file, kept on a Docker volume so it survives restarts
# STATIC_DIR: the built React app
ENV DATA_DIR=/srv/data \
    DB_PATH=/var/lib/portfolio/portfolio.db \
    STATIC_DIR=/srv/static
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
