# docker build -f backend/Dockerfile -t estúdio-clip . (executar na raiz)
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app.py ./backend/app.py
COPY config/presets.json ./config/presets.json
WORKDIR /app/backend
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
