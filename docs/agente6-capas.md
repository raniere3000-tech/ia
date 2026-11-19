# Agente 6: capas (thumbnails)

O Agente 6 faz as capas dos cortes do Agente 1 e dos vídeos do Agente 3. Ele trabalha **depois do editor (Agente 5)**, com o arquivo final, e o diretor (Agente 4) confere cada capa antes de você escolher.

Tela: **Criar vídeos > Capas (Agente 6)**, também em **Automação e agentes** e no atalho da Central. Endereço: `#thumbnails`.

## Fluxo

1. Você escolhe o vídeo (corte, vídeo do Agente 3 ou post) pelo id. O site **nunca manda caminho de arquivo**.
2. Com a esteira ligada, o pedido espera o certificado do diretor para o vídeo (`aguardando_video`).
3. A fila pesada (um por vez no celular) roda `agente6.thumbnail`:
   - o FFprobe confere o vídeo (quebrado ou sem imagem: falha, nenhuma capa);
   - o FFmpeg tira de 6 a 12 quadros espalhados, longe do primeiro e do último segundo;
   - os quadros são escolhidos por nitidez, contraste e luz, e precisam ser **diferentes entre si** (hash de imagem);
   - o Pillow desenha de 1 a 4 capas, cada uma com uma composição diferente: tela cheia, faixa, dividido, moldura ou texto no topo;
   - o texto é sempre desenhado pelo EstúdioClip com a fonte Inter (licença OFL), nunca pela IA. Emoji é tirado, porque a fonte não tem.
4. O diretor confere cada capa e dá uma nota de 0 a 100:

   | Critério | Pontos |
   |---|---|
   | Fiel ao vídeo | 25 |
   | Leitura no celular | 20 |
   | Área segura | 15 |
   | Arquivo | 15 |
   | Identidade | 15 |
   | Formato da rede | 10 |

   - A leitura no celular é medida de verdade na capa reduzida a 120 px: o contraste entre as letras e o fundo, e a altura da letra.
   - Um bloqueio reprova a capa mesmo com nota alta. São bloqueios: arquivo que não abre, tamanho errado, mais de 2 MB, texto que não cabe e texto fora da área segura.
   - Capa reprovada ganha uma correção localizada: caixa escura atrás do texto e texto mais curto. Isso vale até o máximo de correções configurado (padrão 5), e o vídeo não é refeito.
5. A escolha depende do modo:
   - **Automático:** escolhe sozinho a melhor capa aprovada.
   - **Supervisionado:** você escolhe.
   - **Manual:** só faz capa quando você pede.

   Uma capa abaixo da nota só é usada com a sua confirmação. Uma capa com bloqueio nunca é usada.
6. A escolha cria o pacote: vídeo + capa + metadados, preso ao SHA-256 dos dois. Se o vídeo mudar, a escolha cai. Se a capa mudar, a aprovação cai. Escolher uma capa nova para o mesmo vídeo derruba a anterior.
7. O evento `thumbnail.pacote_pronto` fica registrado. O Coordenador (Agente 7), no futuro, entra entre esse evento e a liberação ao Agente 2.

## Redes

A capa nunca passa por cima dos portões do Agente 2. Ela só vai junto quando o post sai pelo caminho de sempre.

| Rede | Tipo | O que acontece |
|---|---|---|
| YouTube | envio da imagem | `thumbnails.set` logo depois do vídeo. Se o YouTube recusar (ex.: conta sem verificação), o vídeo continua postado e o post ganha uma nota. Em Shorts, o feed pode mostrar outro quadro. |
| TikTok | só o momento | `video_cover_timestamp_ms` com o segundo do quadro da capa, só no modo "postar direto". |
| Instagram | só o momento | `thumb_offset` no Reels. Para usar a arte, baixe a capa e troque no app. |
| Facebook / Kwai | manual | Baixe a capa. |

Uma rede só aparece como "funcionou num envio real" depois de um envio que deu certo. Até lá aparece como "não testado com conta real".

A opção **"Só postar no YouTube com capa escolhida"** (desligada por padrão) faz o Agente 2 barrar o YouTube sem capa aprovada para o arquivo.

## IA (opcional, desligada por padrão)

O método **Com IA** usa o gerador de imagens do Gemini (chave de "imagens") só para o **fundo**. O texto continua pelo desenho próprio.

- O custo é estimado em US$ 0,04 por imagem, a mesma estimativa do Agente 3.
- Há um limite de imagens por pedido.
- Sem chave, ou com a IA desligada, o pedido volta com o erro 503 e uma orientação. Com "usar o jeito local se a IA não der" (marcado no pedido ou salvo nas Configurações), o Agente 6 faz com quadros do vídeo e avisa.

## Segurança

- O vídeo é achado pelo id dentro da pasta de dados (`resolve` + checagem de pasta). Referências como `../` são recusadas.
- O FFmpeg roda com lista de argumentos, sem shell, com tempo limite e `check=True`. O texto nunca entra em comando.
- As imagens são gravadas em arquivo temporário e trocadas de uma vez (`os.replace`). Cada uma é conferida com `PIL.verify`. Há um limite de pixels contra imagem "bomba".
- As imagens só abrem com sessão ou com link assinado temporário (3 h).
- O pedido repetido (duplo clique) devolve o mesmo pedido. Depois de um reinício, as capas já gravadas não são refeitas.

## API (`/api/v1/thumbnails`, com sessão)

| Rota | Para quê |
|---|---|
| `GET /fontes?origem=&termo=` | Vídeos que podem ganhar capa |
| `GET /jobs?estado=` e `POST /jobs` | Lista e pedido (`origem`, `referencia`, `metodo`, `variantes`, `formato`, `texto_modo`, `texto`, `descricao`, `perfil_id`, `fallback_local`) |
| `GET /jobs/{id}` | Progresso, tempos, variantes com links assinados e laudos |
| `POST /jobs/{id}/cancelar` | Cancela o pedido |
| `POST /jobs/{id}/refazer` | `{numero, texto?}`: refaz só uma capa |
| `POST /jobs/{id}/selecionar` | `{variante_id, versao, confirmacao}` |
| `GET /jobs/{id}/pacote` (ou `POST /jobs/{id}/validar`) | O pacote, conferido de novo |
| `GET/POST /perfis` e `PATCH /perfis/{id}` | Modelos de marca: cores, escurecido, maiúsculas, logo (id de arquivo da biblioteca), escopo `geral`, `perfil:`, `linha:` ou `canal:` |
| `GET/POST /config`, `GET /capacidades`, `GET /desempenho` | Configurações, o que cada rede aceita e os tempos |
| `GET /midia/{variante}` | A imagem (`&baixar=1` para baixar) |

Os erros usam estes códigos:

| Código | Quando |
|---|---|
| 400 | Pedido inválido |
| 401/403 | Sem sessão ou fora da pasta |
| 404 | Não encontrado |
| 409 | Versão mudou ou bloqueio |
| 429 | Limite de refações |
| 503 | IA indisponível |

## Desempenho

Mostra só o que foi medido: tempo trabalhando, espera na fila, previsão por pedido (média deste servidor), falhas, tentativas técnicas, correções do diretor, custo estimado e quais composições você escolhe. **Não há CTR**: as redes não devolvem isso por aqui. A nota também não prevê cliques. Comparar capas aqui não é teste A/B oficial de nenhuma rede.

## Banco

A migração 10 é só aditiva e cria estas tabelas:

- `thumbnail_jobs`
- `thumbnail_variantes`
- `thumbnail_selecoes`
- `thumbnail_perfis`

## Skills externas da especificação

Nenhuma foi instalada nem roda código: kajisho5/thumbnail-skill, smart-thumbnailer, NanoThumbnail, rembg e as outras.

- A versão 1 é FFmpeg + Pillow, que já estão no servidor.
- As ideias usadas foram escritas aqui: escolha de quadros nítidos e diferentes, composição editorial e legibilidade em tamanho pequeno.
- Para integrar uma skill de verdade, é preciso conferir a licença, o commit e o custo no Termux, e ela entra como adaptador pelo registro de ferramentas (`integracoes.py`).

## Testes

`servidor/testes/teste_thumbnails.py` usa o servidor HTTP de verdade, o FFmpeg, o Pillow e um YouTube falso. São 96 conferências.

**Não testado no celular, nem com o YouTube, o TikTok ou o Instagram de verdade.**
