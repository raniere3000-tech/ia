#!/data/data/com.termux/files/usr/bin/bash
# EstúdioClip no Android (Termux). Rode:  bash iniciar-termux.sh
# Opções:  bash iniciar-termux.sh link   -> cria também um endereço https para usar de outro aparelho
set -e
cd "$(dirname "$0")"
if [ ! -f .instalado ]; then
  echo "Primeira vez: instalando (uns 3 minutos)..."
  pkg update -y
  pkg install -y python ffmpeg nodejs
  [ "$1" = "link" ] && pkg install -y cloudflared
  pip install -U yt-dlp yt-dlp-ejs
  touch .instalado
else
  pip install -q -U yt-dlp yt-dlp-ejs || true   # mantém o yt-dlp em dia (o YouTube muda sempre)
fi
command -v termux-wake-lock >/dev/null && termux-wake-lock || true   # não deixa o Android dormir no meio do download

if [ "$1" = "link" ]; then
  command -v cloudflared >/dev/null || pkg install -y cloudflared
  if [ -z "$TOKEN" ]; then
    [ -f .senha ] || head -c 9 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' > .senha
    export TOKEN="$(cat .senha)"
  fi
  echo
  echo "  SENHA do servidor: $TOKEN   (cole no site, em Chaves e ajustes)"
  echo "  Criando o endereço https (leva uns segundos)..."
  echo
  python servidor.py &
  SRV=$!
  trap 'kill $SRV 2>/dev/null' EXIT
  sleep 2
  SITE="${SITE:-https://raniere3000-tech.github.io/ia/}"
  cloudflared tunnel --no-autoupdate --url http://localhost:${PORTA:-8787} 2>&1 | while read -r linha; do
    URL=$(echo "$linha" | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' || true)
    if [ -n "$URL" ]; then
      echo
      echo "  ============================================================"
      echo "  Servidor no ar: $URL"
      echo "  Abra este link em qualquer aparelho (PC, outro celular):"
      echo
      echo "  ${SITE}?servidor=${URL}&senha=${TOKEN}"
      echo
      echo "  Ele abre o site já ligado ao servidor deste celular."
      echo "  O link muda quando você reinicia o servidor."
      echo "  ============================================================"
      command -v termux-clipboard-set >/dev/null && echo "${SITE}?servidor=${URL}&senha=${TOKEN}" | termux-clipboard-set && echo "  (link copiado)"
    fi
  done
else
  python servidor.py
fi
