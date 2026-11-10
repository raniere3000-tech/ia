# Para hospedar (Render, Railway, VPS). Atenção: o YouTube costuma bloquear servidores de nuvem;
# no seu próprio computador funciona melhor. Defina TOKEN para ninguém mais usar seu servidor.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY servidor.py .
ENV HOST=0.0.0.0 PORT=8787
EXPOSE 8787
CMD ["python", "servidor.py"]
