#!/usr/bin/env bash
# EstúdioClip: servidor que baixa vídeos do YouTube pelo link para o site cortar sozinho.
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Instale o Python 3: https://www.python.org/downloads/"; exit 1; }
if [ ! -d .venv ]; then echo "Primeira vez: instalando o servidor (leva 1 a 3 minutos)..."; python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -U -r requirements.txt
python servidor.py
