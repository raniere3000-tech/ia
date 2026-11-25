# F4.03 — inventário e snapshots reais

O inventário exposto no painel descreve capacidade do código, sem afirmar acesso
à conta. Nenhuma consulta a contas reais foi feita nesta execução.

| Rede | Consulta existente | Limite |
| --- | --- | --- |
| YouTube | videos, statistics; views/likes/comments | readonly solicitado; autorização efetiva não verificada; sem retenção |
| Instagram | media, like_count/comments_count | instagram_basic e pages_read_engagement solicitados; sem views/retencão neste coletor |
| Facebook | vídeo, views/likes/comments | views só quando retornadas; Video Insights não implementado |
| TikTok | nenhum coletor | video.list não solicitado; publish_id não comprova ID público |
| Kwai | nenhum coletor | sem integração |

Documentação primária consultada em 24/11/2026:
- https://developers.google.com/youtube/data/reference/rest/v3/videos?hl=en
- https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/v21.0/
- https://developers.facebook.com/docs/graph-api/reference/video/video_insights/
- https://developers.tiktok.com/doc/tiktok-api-v2-video-query/

A versão Graph configurada continua v24.0. Não foram ampliados escopos OAuth.
Retenção não é coletada. Ausência, erro HTTP e permissão desconhecida não viram zero.
Zero efetivamente retornado é válido. Contagens inválidas são descartadas.

`METRICAS_PUBLICACOES=0` mantém a ampliação desligada por padrão. Quando ligada,
publicações IA/manuais alimentam a tabela existente, com rede e data da medição.
A camada HTTP/coletor injeta os posts: aprendizado não chama postagem. Cortes já
representados não são duplicados por post/rede. Legados sem data de medição ficam
sem essa data; não se inventa uma leitura histórica.

Validação: 7 testes novos, aprendizado 47 verificações e painel 34 verificações
passaram. São dados simulados e banco temporário, sem contas reais.
