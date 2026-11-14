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

## Agentes (cortes e postagem sozinhos)

O servidor traz dois agentes, configurados na aba **Agentes** do site:

- **Agente de cortes**: sugere canais em alta no seu nicho, acha vídeos novos dos canais que você aprovou, baixa, escolhe os melhores trechos com IA, edita em vertical (legenda, gancho, tarjas, variações sorteadas) e manda cada corte por e-mail.
- **Agente de postagem**: agenda os cortes prontos nas redes, nos horários que você marcou, avisa por e-mail e passa a preferir os horários que renderam mais visualizações no YouTube.

Para funcionar, na aba Agentes:

1. Em **Avisos e chaves**, guarde a chave do Gemini e a chave do YouTube no servidor, o e-mail que recebe, o e-mail que envia e a **senha de aplicativo** dele (no Gmail: Conta Google > Segurança > Senhas de app). Toque em Enviar e-mail de teste.
2. Em **Cortes**, toque em Procurar canais e aprove os canais marcando o motivo (é seu, o dono autorizou ou o canal tem regra pública de cortes). O agente não corta canal sem motivo marcado.
3. Em **Postagem**, marque as redes e os horários. As contas são as mesmas de Agendar posts.
4. Ligue os dois agentes. O botão **Parar tudo** desliga os dois e tira da agenda os posts que eles marcaram.

### Templates compartilhados

Os modelos de vídeo ficam na aba **Templates** do site e são gravados também no servidor (`~/.estudioclip/modelos.json`). A edição manual e os agentes usam a mesma biblioteca.

- Marque até **3 templates** para os agentes (na aba Templates ou em Agentes > Cortes). O agente sorteia um para cada corte, com chances iguais no começo.
- Com o **aprendizado** ligado, os pesos mudam aos poucos conforme o resultado de cada rede (visualizações; onde a rede não entrega, curtidas e comentários). Nenhum template cai abaixo de 15%. Você também pode definir os pesos à mão em Agentes > Desempenho.
- O template de cada vídeo fica registrado no post, inclusive nos cortes que você manda da edição manual (Salvar como pronto ou Enviar à fila do agente).
- Antes de publicar, o servidor confere: canal de origem aprovado, permissão comercial, arquivo repetido e trecho já postado. O que não passa fica parado esperando você.
- O site desenha a prévia e o vídeo manual no navegador; o agente monta com FFmpeg seguindo os mesmos campos do template. Pequenas diferenças de letra entre os dois são esperadas. Zoom lento e as duas transições funcionam nos dois; tremor de câmera, seguir o rosto e câmera acelerada são só da edição manual.
- Retenção e receita não são lidas: as redes só entregam esses números com permissões extras de análise.

No celular, para os agentes trabalharem sem parar:

```
bash iniciar-termux.sh link     # liga o servidor, com vigia que religa se ele cair
bash iniciar-termux.sh sempre   # liga sozinho quando o celular reinicia (app Termux:Boot)
```

Deixe o celular na tomada e tire o Termux da economia de bateria. As chaves, a senha do e-mail e os cortes ficam só na pasta `~/.estudioclip` do aparelho. A letra das legendas é a fonte Inter (licença em `fontes/LICENCA-Inter.txt`).

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

## Segurança

- **Senhas e chaves criptografadas no servidor.** Os logins das redes (`contas.json`), as chaves do agente (`agente_segredos.json`) e os cookies do YouTube ficam cifrados em disco. A chave-mestra fica em `~/.estudioclip-chave`, criada sozinha na primeira vez. Arquivos antigos em texto puro são convertidos na primeira leitura. Se apagar a chave-mestra, é preciso refazer os logins e as chaves.
- **Limite honesto:** a chave-mestra fica no mesmo aparelho. Isso protege contra cópia dos arquivos, backup e envio acidental, mas não contra quem tem acesso total ao celular desbloqueado. Use bloqueio de tela.
- **Senha do servidor:** mínimo de 10 caracteres (`bash iniciar-termux.sh senha`). Ela só é aceita no cabeçalho, nunca no endereço. Depois de 8 senhas erradas em 10 minutos o visitante fica bloqueado.
- **Link fixo assinado:** o endereço anunciado no canal vai assinado com a senha, e o site só troca de endereço sozinho se a assinatura conferir. O link fixo leva a senha depois do `#`, que não é enviado para nenhum servidor.
- **Sem senha, só local:** o servidor se recusa a abrir para a rede sem `TOKEN`.
- **No site:** em Chaves e ajustes, "Proteger as chaves com PIN" cifra as chaves guardadas no navegador (AES-GCM, PIN esticado com PBKDF2). Sem o PIN não há como recuperar: é preciso colar as chaves de novo.
