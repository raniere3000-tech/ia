#!/data/data/com.termux/files/usr/bin/bash
# EstúdioClip no Android (Termux). Rode:  bash iniciar-termux.sh
# Opções:  bash iniciar-termux.sh link    -> cria também um endereço https para usar de outro aparelho (link fixo)
#          bash iniciar-termux.sh senha   -> escolhe uma senha nova para o servidor
#          bash iniciar-termux.sh sempre  -> liga sozinho quando o celular reinicia (precisa do app Termux:Boot)
#          bash iniciar-termux.sh parear  -> gera um código de uso único (10 min) para conectar mais um aparelho
#          bash iniciar-termux.sh diagnostico -> mede o celular (ficha + render de 5 s + prévia leve); não instala nada
#          bash iniciar-termux.sh linkfixo TOKEN https://estudio.seudominio.com.br -> endereço que nunca muda (túnel com nome da Cloudflare)
#          bash iniciar-termux.sh whatsapp 5511912345678 -> liga o seu WhatsApp (comandos e avisos na conversa com você mesmo)
set -e
cd "$(dirname "$0")"
if [ "$1" = "senha" ]; then
  read -r -s -p "Digite a nova senha (só letras e números, mínimo 10): " NOVA; echo
  if ! echo "$NOVA" | grep -Eq '^[A-Za-z0-9]{10,60}$'; then echo "Senha inválida. Use só letras e números, de 10 a 60."; exit 1; fi
  ( umask 077; printf '%s' "$NOVA" > .senha ); chmod 600 .senha
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
if [ "$1" = "parear" ]; then
  [ -f .senha ] && export TOKEN="${TOKEN:-$(cat .senha)}"
  R=$(curl -s -m 10 -X POST -H "X-Token: ${TOKEN}" -H 'Content-Type: application/json' -d '{"nome":"Aparelho novo"}' "http://localhost:${PORTA:-8787}/api/v1/pareamento/iniciar" || true)
  COD=$(echo "$R" | grep -o '"codigo": *"[A-Z0-9-]*"' | grep -o '[A-Z0-9]\{4\}-[A-Z0-9]\{4\}' || true)
  if [ -z "$COD" ]; then echo "O servidor precisa estar ligado (bash iniciar-termux.sh link em outra sessão)."; exit 1; fi
  SITE="${SITE:-https://raniere3000-tech.github.io/ia/}"
  CANAL="$(cat .canal 2>/dev/null || true)"
  echo "  Código: $COD  (vale 10 minutos, uma vez só)"
  URLA="$(cat .url_atual 2>/dev/null || true)"
  if [ -n "$URLA" ]; then echo "  Link para o aparelho novo: ${SITE}?servidor=${URLA}&canal=${CANAL}#par=${COD}"
  else echo "  O endereço do servidor ainda não saiu. Espere o túnel ligar e rode de novo, ou gere o link no site em Ajustes > Aparelhos."; fi
  exit 0
fi
if [ "$1" = "linkfixo" ]; then
  # Endereço fixo: crie o túnel no painel da Cloudflare (Zero Trust > Networks > Tunnels), aponte o seu
  # endereço (ex.: estudio.seudominio.com.br) para http://localhost:8787 e cole aqui o token e o endereço.
  if [ "$2" = "desligar" ]; then rm -f .tunel_token .url_fixa; echo "Voltou para o endereço que muda (trycloudflare)."; exit 0; fi
  TK="$2"; UF="$(echo "$3" | sed 's#/*$##')"
  case "$UF" in http*) ;; *) [ -n "$UF" ] && UF="https://$UF";; esac
  if [ ${#TK} -lt 50 ] || ! echo "$UF" | grep -Eq '^https://[a-z0-9.-]+\.[a-z]{2,}$'; then
    echo "Use:  bash iniciar-termux.sh linkfixo TOKEN_DO_TUNEL https://estudio.seudominio.com.br"; exit 1; fi
  ( umask 077; printf '%s' "$TK" > .tunel_token; printf '%s' "$UF" > .url_fixa ); chmod 600 .tunel_token .url_fixa
  echo "Endereço fixo salvo: $UF"
  echo "Agora ligue:  bash iniciar-termux.sh link"
  exit 0
fi
# Ponte do WhatsApp Web: instala as dependências (uma vez, e de novo quando mudarem depois de um git pull).
ponte_deps() {
  command -v node >/dev/null || pkg install -y nodejs
  if [ ! -f whatsapp-ponte/node_modules/.ok ] || [ whatsapp-ponte/package.json -nt whatsapp-ponte/node_modules/.ok ]; then
    echo "  Instalando a ponte do WhatsApp (uma vez, leva 1 a 2 minutos)..."
    ( cd whatsapp-ponte && npm install --omit=dev --no-audit --no-fund && touch node_modules/.ok )
  fi
}
ZAP_MARCA="${DADOS:-$HOME/.estudioclip}/whatsapp-ligado"
if [ "$1" = "whatsapp" ]; then
  NUM=$(echo "$2" | tr -dc '0-9')
  if [ ${#NUM} -lt 12 ]; then echo "Use:  bash iniciar-termux.sh whatsapp 5511912345678   (55 + DDD + número, só o seu)"; exit 1; fi
  ponte_deps
  pkill -f "ponte-estudioclip" 2>/dev/null || true
  pkill -f "whatsapp-ponte/ponte.mjs" 2>/dev/null || true
  node whatsapp-ponte/ponte.mjs --parear "$NUM"
  echo
  echo "  WhatsApp ligado. Agora ligue o servidor de novo:  bash iniciar-termux.sh link"
  echo "  Depois mande \"ajuda\" na conversa com você mesmo no WhatsApp."
  exit 0
fi
if [ "$1" = "skills" ]; then
  command -v python >/dev/null || { echo "Falta o Python. Rode:  pkg install -y python"; exit 1; }
  python -m skills.relatorio $2
  exit $?
fi
if [ "$1" = "diagnostico" ]; then
  command -v python >/dev/null || { echo "Falta o Python. Rode:  pkg install -y python"; exit 1; }
  python diagnostico_aparelho.py $2
  exit $?
fi
if [ ! -f .instalado ]; then
  echo "Primeira vez: instalando (uns 3 minutos)..."
  pkg update -y
  pkg install -y python ffmpeg nodejs tmux curl
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
pkill -f "ponte-estudioclip" 2>/dev/null || true
pkill -f "whatsapp-ponte/ponte.mjs" 2>/dev/null || true
command -v termux-wake-lock >/dev/null && termux-wake-lock || true   # não deixa o Android dormir no meio do download

if [ "$1" = "link" ]; then
  command -v cloudflared >/dev/null || pkg install -y cloudflared
  if [ -z "$TOKEN" ]; then
    [ -f .senha ] || ( umask 077; head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24 > .senha )
    chmod 600 .senha
    export TOKEN="$(cat .senha)"
  fi
  command -v curl >/dev/null || pkg install -y curl
  # Canal fixo: o servidor avisa o endereço novo nele toda vez que liga, e o site acha sozinho.
  [ -f .canal ] || ( umask 077; head -c 30 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 20 > .canal )
  chmod 600 .canal
  CANAL="$(cat .canal)"
  TOPICO="https://ntfy.sh/estudioclip-${CANAL}"
  SITE="${SITE:-https://raniere3000-tech.github.io/ia/}"
  # Segredo do aviso: os aparelhos pareados recebem este segredo (e não a senha) para conferir o endereço novo.
  [ -s .anuncio ] || ( umask 077; head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' > .anuncio )
  chmod 600 .anuncio
  # O aviso vai assinado duas vezes (senha e segredo do aviso): quem descobrir o canal não aponta o site para outro servidor.
  assinar() { python -c 'import hmac,hashlib,sys; u=sys.argv[1]; print(u+"|"+hmac.new(sys.argv[2].encode(),u.encode(),hashlib.sha256).hexdigest()+"|"+hmac.new(sys.argv[3].encode(),u.encode(),hashlib.sha256).hexdigest())' "$1" "$TOKEN" "$(cat .anuncio)"; }
  # Link para conectar um aparelho: código de USO ÚNICO que vence em 10 minutos (a senha nunca vai no link).
  link_par() { C=$(curl -s -m 10 -X POST -H "X-Token: ${TOKEN}" -H 'Content-Type: application/json' -d '{"nome":"Aparelho novo"}' "http://localhost:${PORTA:-8787}/api/v1/pareamento/iniciar" | grep -o '[A-Z0-9]\{4\}-[A-Z0-9]\{4\}' | head -1); [ -n "$C" ] && echo "${SITE}?servidor=${1}&canal=${CANAL}#par=${C}"; }
  echo
  echo "  SENHA do servidor: $TOKEN"
  echo "  Criando o endereço https (leva uns segundos)..."
  echo
  rm -f .url_atual
  # Vigia: se o servidor cair (os agentes trabalham por horas), liga de novo em 5 segundos.
  bash -c 'while true; do python servidor.py; sleep 5; done # vigia-estudioclip' &
  SRV=$!
  # WhatsApp (se você já ligou com: bash iniciar-termux.sh whatsapp SEU_NUMERO): comandos e avisos na conversa com você mesmo.
  if [ -f "$ZAP_MARCA" ]; then
    ponte_deps || true
    bash -c 'while true; do node whatsapp-ponte/ponte.mjs; [ $? = 2 ] && break; sleep 10; done # ponte-estudioclip' &
    echo "  WhatsApp: ponte ligada (mande \"ajuda\" na conversa com você mesmo)."
  fi
  # Repete o aviso a cada 6 horas (o canal esquece mensagens depois de 12 horas).
  ( while sleep 21600; do [ -f .url_atual ] && curl -s -m 20 -d "$(assinar "$(cat .url_atual)")" "$TOPICO" >/dev/null; done ) &
  PUB=$!
  # Vigia do túnel: se o endereço deixar de resolver (o túnel caiu), desliga o cloudflared; o laço abaixo liga de novo
  # e publica o endereço novo no canal (e um link de pareamento novo).
  ( falhas=0; while sleep 60; do
      U=$(cat .url_atual 2>/dev/null); [ -z "$U" ] && continue
      if curl -s -m 15 -o /dev/null "$U/api/v1/saude"; then falhas=0; else falhas=$((falhas+1)); fi
      if [ "$falhas" -ge 2 ]; then echo "  (Túnel não responde: reiniciando o endereço...)"; pkill -x cloudflared 2>/dev/null || true; falhas=0; fi
    done ) &
  VIGIA_TUNEL=$!
  trap 'kill $SRV $PUB $VIGIA_TUNEL 2>/dev/null; pkill -f "python servidor.py" 2>/dev/null; pkill -x cloudflared 2>/dev/null; pkill -f "ponte-estudioclip" 2>/dev/null; pkill -f "whatsapp-ponte/ponte.mjs" 2>/dev/null' EXIT
  sleep 2
  while true; do
  # http2 (TCP) em vez de QUIC (UDP): muitas redes de celular e Wi-Fi bloqueiam UDP e o link dá "Erro 1033".
  rm -f .tunel_avisado
  if [ -s .tunel_token ] && [ -s .url_fixa ]; then
    # Endereço FIXO (túnel com nome, no seu domínio da Cloudflare): sempre o mesmo link.
    FIXA="$(cat .url_fixa)"
    TUNEL_CMD="cloudflared tunnel --no-autoupdate --protocol ${TUNEL_PROTOCOLO:-http2} run --token $(cat .tunel_token)"
  else
    FIXA=""
    TUNEL_CMD="cloudflared tunnel --no-autoupdate --protocol ${TUNEL_PROTOCOLO:-http2} --url http://localhost:${PORTA:-8787}"
  fi
  $TUNEL_CMD 2>&1 | tee -a "$HOME/cloudflared.log" | while read -r linha; do
    if [ -n "$FIXA" ]; then
      URL=""
      if echo "$linha" | grep -q 'Registered tunnel connection' && [ ! -f .tunel_avisado ]; then touch .tunel_avisado; URL="$FIXA"; fi
    else
      URL=$(echo "$linha" | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' || true)
    fi
    if [ -n "$URL" ]; then
      echo "$URL" > .url_atual
      sleep 3
      if curl -s -m 20 -d "$(assinar "$URL")" "$TOPICO" >/dev/null; then AVISO="ok"; else AVISO=""; fi
      echo
      echo "  ============================================================"
      echo "  Servidor no ar: $URL"
      echo
      LINK_PAR="$(link_par "$URL" || true)"
      echo "  CONECTAR UM APARELHO (vale 10 minutos, uma vez só):"
      echo
      echo "  ${LINK_PAR:-gere com: bash iniciar-termux.sh parear}"
      echo
      echo "  Aparelho já conectado não precisa de nada: o site acha o servidor"
      echo "  sozinho pelo canal, mesmo quando o endereço muda."
      echo "  Para outro aparelho depois: Ajustes > Aparelhos no site, ou  bash iniciar-termux.sh parear"
      [ -z "$AVISO" ] && echo "  (Aviso: não consegui publicar o endereço no canal. Endereço desta vez: ${URL} )"
      echo "  ============================================================"
      [ -n "$LINK_PAR" ] && command -v termux-clipboard-set >/dev/null && echo "${LINK_PAR}" | termux-clipboard-set && echo "  (link copiado)"
    fi
  done || true
  echo "  O túnel parou. Ligando de novo em 5 segundos (vai sair um endereço novo)..."
  sleep 5
  done
else
  python servidor.py
fi
