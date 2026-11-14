#!/data/data/com.termux/files/usr/bin/bash
# EstúdioClip no Android (Termux). Rode:  bash iniciar-termux.sh
# Opções:  bash iniciar-termux.sh link    -> cria também um endereço https para usar de outro aparelho (link fixo)
#          bash iniciar-termux.sh senha   -> escolhe uma senha nova para o servidor
#          bash iniciar-termux.sh sempre  -> liga sozinho quando o celular reinicia (precisa do app Termux:Boot)
set -e
cd "$(dirname "$0")"
if [ "$1" = "senha" ]; then
  read -r -p "Digite a nova senha (só letras e números, mínimo 6): " NOVA
  if ! echo "$NOVA" | grep -Eq '^[A-Za-z0-9]{6,40}$'; then echo "Senha inválida. Use só letras e números, de 6 a 40."; exit 1; fi
  printf '%s' "$NOVA" > .senha
  echo "Senha salva. Agora rode:  bash iniciar-termux.sh link   e abra o link novo que aparecer."
  exit 0
fi
if [ "$1" = "sempre" ]; then
  mkdir -p "$HOME/.termux/boot"
  printf '#!/data/data/com.termux/files/usr/bin/bash\ntermux-wake-lock\ncd "%s" && bash iniciar-termux.sh link >> "$HOME/estudioclip.log" 2>&1\n' "$(pwd)" > "$HOME/.termux/boot/estudioclip"
  chmod +x "$HOME/.termux/boot/estudioclip"
  echo "Pronto. Instale o app Termux:Boot (F-Droid), abra uma vez, e o servidor liga sozinho quando o celular reiniciar."
  echo "Tire também o Termux da economia de bateria: Ajustes do Android > Apps > Termux > Bateria > Sem restrição."
  exit 0
fi
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
# Se já tem um servidor ligado (outra sessão do Termux), desliga antes para não dar "Address already in use".
pkill -f "vigia-estudioclip" 2>/dev/null || true
pkill -f "python servidor.py" 2>/dev/null && sleep 1 || true
pkill -x cloudflared 2>/dev/null || true
command -v termux-wake-lock >/dev/null && termux-wake-lock || true   # não deixa o Android dormir no meio do download

if [ "$1" = "link" ]; then
  command -v cloudflared >/dev/null || pkg install -y cloudflared
  if [ -z "$TOKEN" ]; then
    [ -f .senha ] || head -c 9 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' > .senha
    export TOKEN="$(cat .senha)"
  fi
  command -v curl >/dev/null || pkg install -y curl
  # Canal fixo: o servidor avisa o endereço novo nele toda vez que liga, e o site acha sozinho.
  [ -f .canal ] || head -c 30 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 20 > .canal
  CANAL="$(cat .canal)"
  TOPICO="https://ntfy.sh/estudioclip-${CANAL}"
  SITE="${SITE:-https://raniere3000-tech.github.io/ia/}"
  LINK_FIXO="${SITE}?canal=${CANAL}&senha=${TOKEN}"
  echo
  echo "  SENHA do servidor: $TOKEN"
  echo "  Criando o endereço https (leva uns segundos)..."
  echo
  rm -f .url_atual
  # Vigia: se o servidor cair (os agentes trabalham por horas), liga de novo em 5 segundos.
  bash -c 'while true; do python servidor.py; sleep 5; done # vigia-estudioclip' &
  SRV=$!
  # Repete o aviso a cada 6 horas (o canal esquece mensagens depois de 12 horas).
  ( while sleep 21600; do [ -f .url_atual ] && curl -s -m 20 -d "$(cat .url_atual)" "$TOPICO" >/dev/null; done ) &
  PUB=$!
  trap 'kill $SRV $PUB 2>/dev/null; pkill -f "python servidor.py" 2>/dev/null' EXIT
  sleep 2
  cloudflared tunnel --no-autoupdate --url http://localhost:${PORTA:-8787} 2>&1 | while read -r linha; do
    URL=$(echo "$linha" | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' || true)
    if [ -n "$URL" ]; then
      echo "$URL" > .url_atual
      sleep 3
      if curl -s -m 20 -d "$URL" "$TOPICO" >/dev/null; then AVISO="ok"; else AVISO=""; fi
      echo
      echo "  ============================================================"
      echo "  Servidor no ar: $URL"
      echo
      echo "  SEU LINK FIXO (não muda mais, pode salvar nos favoritos):"
      echo
      echo "  ${LINK_FIXO}"
      echo
      echo "  Abra em qualquer aparelho. Mesmo quando o servidor reinicia,"
      echo "  é só abrir ou recarregar o site que ele acha o servidor sozinho."
      [ -z "$AVISO" ] && echo "  (Aviso: não consegui publicar o endereço no canal. Use este link desta vez:"
      [ -z "$AVISO" ] && echo "   ${SITE}?servidor=${URL}&senha=${TOKEN} )"
      echo "  ============================================================"
      command -v termux-clipboard-set >/dev/null && echo "${LINK_FIXO}" | termux-clipboard-set && echo "  (link copiado)"
    fi
  done
else
  python servidor.py
fi
