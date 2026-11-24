# Download de vídeos em lote (Publicações)

Em **Publicações > Posts e contas**, marque os vídeos (um, vários, ou "Selecionar todos do filtro") e toque em **Baixar selecionados (N)**, ao lado de **Agendar selecionados (N)**.

## Formatos
- **Pacote completo (ZIP)** — recomendado. Uma pasta por vídeo: `001 - Título - a1b2c3.mp4`, `..._CAPA.png|jpg` e `..._PUBLICACAO.txt`.
- **ZIP só com vídeos** — os MP4, com os mesmos nomes.
- **MP4 individuais** — um arquivo por vídeo, baixados um de cada vez.

## O que entra
- Vale vídeo pendente, agendado ou publicado, desde que o arquivo final exista no servidor. A seleção vale só para a lista do filtro atual (até 300 por vez; o agendamento em lote continua em 200).
- O MP4 é o arquivo final que já está no servidor: nada é renderizado de novo nem baixado de novo da origem, nenhum agente é acionado, nenhuma rede é chamada.
- Capa: só a aprovada para a versão final (hash do arquivo). Sem capa ou com capa de versão antiga, o MP4 e o TXT vêm mesmo assim e o `RELATORIO.txt` avisa.
- TXT: título, descrição, hashtags e links de cada rede do post, só com o que já está salvo. TikTok usa o texto próprio do TikTok. O que não existe aparece como `[não configurado]`.
- Resultado parcial (vídeo sumiu, post removido): o ZIP vem com o que existe, a tela diz "parcial" e o `RELATORIO.txt` lista o que ficou de fora.

## Segurança e limpeza
- O site só manda IDs de post; o caminho do arquivo vem do registro do servidor. Os links de download são assinados (6 h) e não levam a senha.
- Nomes de arquivo sem emoji nem caracteres proibidos no Android/Windows (o título original fica dentro do TXT).
- Um preparo por vez; confere espaço livre (folga de 200 MB); cancelar apaga os temporários; arquivos prontos somem em 24 h. Nunca apaga vídeo original, nunca muda status, horário ou capa de nenhum post.
- Transferência interrompida: o navegador pode retomar (HTTP Range) ou você toca em "Tentar novamente".

## Atualizar o servidor
```bash
cd ~/ia && git pull
cd servidor && bash iniciar-termux.sh link
```
Não há migração de banco nem dependência nova.

## Testes
`cd servidor && PYTHONPATH=. python3 testes/teste_download_lote.py` (65 ok) e, no site, `frontend/testes/e2e-download.cjs` (ver o cabeçalho de `e2e-download-servidor.py`).
