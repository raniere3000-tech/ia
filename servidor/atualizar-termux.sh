#!/data/data/com.termux/files/usr/bin/bash
# Atualiza o EstúdioClip no celular (Termux) e liga o servidor de novo, num comando só:
#   bash ~/ia/servidor/atualizar-termux.sh
# Passos: segura o celular acordado, para servidor/túnel/vigia, atualiza o cloudflared,
# volta para a main, baixa o código novo e inicia no modo link.
# Recursos desligados de propósito? Ex.:  RENDER_INTEGRIDADE=0 bash atualizar-termux.sh
cd "$(dirname "$0")/.." || exit 1
RAIZ="$(pwd)"
command -v termux-wake-lock >/dev/null && termux-wake-lock || true
pkill -f vigia-estudioclip 2>/dev/null || true
pkill -x cloudflared 2>/dev/null || true
pkill -f "python servidor.py" 2>/dev/null || true
command -v pkg >/dev/null && pkg upgrade -y cloudflared || echo "(pkg não encontrado: pulei o cloudflared)"
git checkout main || { echo "Não consegui trocar para a main. Guarde ou descarte suas mudanças locais e tente de novo."; exit 1; }
git pull --ff-only || { echo "git pull falhou. Veja a mensagem acima."; exit 1; }
echo "Versão em uso: $(git log -1 --format='%h %s')"
cd "$RAIZ/servidor" && exec bash iniciar-termux.sh link
