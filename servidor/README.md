# Servidor de cortes pelo link

O site roda todo no navegador, mas nenhum navegador consegue baixar vídeo do YouTube.
Este servidor pequeno faz só isso: recebe o link, baixa o vídeo (até 720p) com o
[yt-dlp](https://github.com/yt-dlp/yt-dlp) e entrega o arquivo para o site, que analisa e corta sozinho.

**Use apenas com vídeos seus ou com autorização do dono.**

## Rodar no seu computador (recomendado)

1. Instale o [Python 3](https://www.python.org/downloads/). No Windows, marque **Add Python to PATH**.
2. Windows: dois cliques em `iniciar-windows.bat`. Mac/Linux: `./iniciar-mac-linux.sh`.
   Na primeira vez ele cria um ambiente e instala tudo (yt-dlp, Deno e FFmpeg vêm pelo pip).
3. Quando aparecer `rodando em http://localhost:8787`, deixe a janela aberta.
4. No site, em **Chaves e ajustes → Cortes direto pelo link do YouTube**, cole `http://localhost:8787` e clique em **Testar e salvar**.

Depois disso, em **Gerar cortes**, colar um link (ou clicar em "Abrir no estúdio" no Radar) já baixa e corta sozinho.

## Rodar no celular Android (Termux)

O IP do celular é residencial, então o YouTube quase nunca bloqueia. No Termux:

```bash
pkg install -y git
git clone https://github.com/raniere3000-tech/ia
cd ia/servidor
bash iniciar-termux.sh          # usar o site no próprio celular: cole http://localhost:8787
bash iniciar-termux.sh link     # usar o site no PC: cria um endereço https e uma senha
```

Com `link`, o terminal mostra a **senha** e um endereço `https://….trycloudflare.com`.
Cole os dois no site, em **Chaves e ajustes**. O endereço muda cada vez que você reinicia.
Se você usa Ubuntu dentro do Termux (proot-distro), use `./iniciar-mac-linux.sh`.
Para atualizar depois: `cd ia && git pull`.

## Agendar posts (YouTube, Instagram, Facebook, TikTok, Kwai)

O mesmo servidor guarda os cortes e publica nas **suas** contas na hora marcada, mesmo com o site fechado
(o servidor precisa estar ligado no horário). Os dados ficam em `~/.estudioclip/` (`contas.json`, `posts.json`, `videos/`).

1. No site, abra **Agendar posts** e copie o **endereço de retorno**.
2. Em cada rede, crie o app de desenvolvedor (botão **Como criar?** de cada card) e cadastre esse endereço.
3. Cole o ID e o segredo no card e clique em **Entrar com minha conta**.
4. Em **Gerar cortes**, clique em **Agendar** no corte, escolha redes, data e hora.

Limites das redes: YouTube com projeto não verificado sobe como privado (peça a auditoria);
TikTok sem aprovação manda para os rascunhos; Kwai não tem API (fica o botão de baixar).

## Configuração (variáveis de ambiente)

| Variável | Padrão | Para quê |
|---|---|---|
| `PORTA` / `PORT` | `8787` | Porta do servidor |
| `HOST` | `127.0.0.1` | Use `0.0.0.0` para hospedar |
| `TOKEN` | vazio | Senha. Se definir, cole a mesma no site |
| `MAX_MINUTOS` | `180` | Duração máxima do vídeo |
| `ALTURA_MAX` | `720` | Resolução máxima baixada |
| `DADOS` | `~/.estudioclip` | Onde ficam contas, posts e vídeos agendados |
| `ORIGENS` | site no GitHub Pages + localhost | Sites que podem usar o servidor |

## Hospedar na nuvem

Tem `Dockerfile` nesta pasta. Defina `TOKEN`. Atenção: o YouTube costuma bloquear
servidores de nuvem ("Sign in to confirm you're not a bot"). No seu computador funciona melhor.

Se um vídeo parar de baixar, atualize o yt-dlp abrindo o iniciador de novo (ele roda `pip install -U`).
