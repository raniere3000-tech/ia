#!/data/data/com.termux/files/usr/bin/bash
# EstúdioClip: entrar no servidor (Termux) a partir de OUTRO aparelho Android.
# Rode no celular que é o servidor:
#   bash acesso-remoto.sh            -> liga o acesso pelo terminal (SSH) e mostra tudo o que o outro aparelho precisa
#   bash acesso-remoto.sh servidor   -> liga o servidor dentro do tmux "estudioclip" (assim dá para vê-lo de outro aparelho)
#   bash acesso-remoto.sh senha      -> troca a senha do acesso pelo terminal
#   bash acesso-remoto.sh desligar   -> desliga o acesso pelo terminal
set -e
cd "$(dirname "$0")"
SESSAO="estudioclip"
PORTA_SSH=8022
MARCA_SENHA="${DADOS:-$HOME/.estudioclip}/ssh-senha-definida"

meu_ip() {
  # Procura o IP do Wi-Fi (192.168.x.x, 10.x.x.x ou 172.16-31.x.x).
  local ips=""
  if command -v ifconfig >/dev/null 2>&1; then
    ips=$(ifconfig 2>/dev/null | grep -o 'inet [0-9.]*' | awk '{print $2}')
  fi
  if [ -z "$ips" ] && command -v ip >/dev/null 2>&1; then
    ips=$(ip -4 addr 2>/dev/null | grep -o 'inet [0-9.]*' | awk '{print $2}')
  fi
  echo "$ips" | grep -E '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' | head -1
}

if [ "$1" = "servidor" ]; then
  command -v tmux >/dev/null || pkg install -y tmux
  if tmux has-session -t "$SESSAO" 2>/dev/null; then
    echo "O servidor já está rodando no tmux \"$SESSAO\". Entrando nele..."
  else
    tmux new-session -d -s "$SESSAO" -c "$(pwd)" "bash iniciar-termux.sh link; echo; echo 'O servidor parou. Aperte Enter para fechar.'; read"
    echo "Servidor ligado dentro do tmux \"$SESSAO\"."
  fi
  echo "Para sair da tela SEM desligar: aperte Ctrl+B, solte, e aperte D."
  sleep 2
  [ -n "$TMUX" ] && exec tmux switch-client -t "$SESSAO"
  exec tmux attach -t "$SESSAO"
fi

if [ "$1" = "desligar" ]; then
  pkill -x sshd 2>/dev/null && echo "Acesso pelo terminal desligado." || echo "O acesso pelo terminal já estava desligado."
  exit 0
fi

# 1) Instala o SSH (uma vez só)
if ! command -v sshd >/dev/null 2>&1; then
  echo "Instalando o acesso pelo terminal (uma vez só, leva menos de 1 minuto)..."
  pkg install -y openssh
fi
command -v ifconfig >/dev/null 2>&1 || pkg install -y net-tools >/dev/null 2>&1 || true

# 2) Senha (pedida só na primeira vez, ou com:  bash acesso-remoto.sh senha)
if [ "$1" = "senha" ] || [ ! -f "$MARCA_SENHA" ]; then
  echo
  echo "Escolha uma senha para entrar pelo outro aparelho."
  echo "(Ao digitar, nada aparece na tela. É normal. Digite e aperte Enter, depois repita.)"
  until passwd; do echo "As senhas não bateram. Tente de novo."; done
  mkdir -p "$(dirname "$MARCA_SENHA")"; touch "$MARCA_SENHA"
fi

# 3) Liga o SSH
pgrep -x sshd >/dev/null 2>&1 || sshd 2>/dev/null || true
command -v termux-wake-lock >/dev/null && termux-wake-lock || true   # não deixa o Android dormir

USUARIO=$(whoami)
IP=$(meu_ip)
URL=$(cat .url_atual 2>/dev/null || true)

echo
echo "  ============================================================"
echo "  ACESSO DE OUTRO ANDROID"
echo
echo "  1) PELO SITE (funciona em qualquer lugar, até fora do Wi-Fi)"
if [ -n "$URL" ]; then
  echo "     Servidor no ar: $URL"
  echo "     Para conectar o outro aparelho, rode aqui:  bash iniciar-termux.sh parear"
  echo "     e abra no outro aparelho o link que aparecer (vale 10 minutos)."
else
  echo "     O servidor não está ligado com link agora. Ligue com:"
  echo "       bash acesso-remoto.sh servidor"
fi
echo
echo "  2) PELO TERMINAL (os dois aparelhos no MESMO Wi-Fi)"
echo "     Usuário: $USUARIO"
if [ -n "$IP" ]; then
  echo "     IP:      $IP"
  echo
  echo "     No outro Android, instale o Termux e rode (uma vez):  pkg install -y openssh"
  echo "     Depois, para entrar:"
  echo
  echo "       ssh -p $PORTA_SSH $USUARIO@$IP"
  echo
  echo "     Digite a senha que você escolheu. Já dentro, para ver o servidor:"
  echo
  echo "       tmux attach -t $SESSAO"
  echo
  echo "     Para sair sem desligar nada: Ctrl+B, solte, e aperte D. Depois digite: exit"
  command -v termux-clipboard-set >/dev/null && echo "ssh -p $PORTA_SSH $USUARIO@$IP" | termux-clipboard-set && echo "     (comando ssh copiado)"
else
  echo "     Não achei o IP do Wi-Fi. Confira se este celular está conectado no Wi-Fi"
  echo "     (dados móveis não servem para este jeito) e rode de novo."
fi
if ! tmux has-session -t "$SESSAO" 2>/dev/null; then
  echo
  echo "     Atenção: o servidor ainda não está no tmux \"$SESSAO\", então o"
  echo "     tmux attach não vai achar nada. Ligue o servidor com:"
  echo "       bash acesso-remoto.sh servidor"
fi
echo "  ============================================================"
