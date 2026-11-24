# F4.01 — Status independente por rede

A inspeção confirmou implementação existente; não foi reescrita:

- `postagem.posts/lista_posts` preservam dicionário de destinos por post.
- `postagem.ciclo` trata falha/travamento de uma rede sem bloquear as demais.
- `postagem.postar_agora(pid, rede)` tenta só o destino pedido.
- `filtrosPosts.corresponde/donoDaRede/filtrarPosts` filtram e agrupam por vídeo
  e destino, usando o horário da própria rede. Destino ainda ausente pode
  aparecer como não agendado quando o arquivo estiver disponível.
- `Agendar.tsx` já tem rede, situação, contagens e ação dirigida à rede.

Ampliação de regressão: YouTube concluído + TikTok com erro + Instagram manual
no mesmo post; filtros não alteram status, link, referência nem data anterior.
Todos os 18 testes frontend passaram; backend redes_independentes 13/13,
incluindo erro, travamento, retry dirigido e preservação da publicação original.
Plataformas simuladas em dados temporários, sem acesso a contas reais.

Nenhuma alteração em módulo do aplicativo, flag, migração ou estado publicado.
Somente testes adicionais e documentação. Próxima: F4.02, lote/retry/slots e
investigação da falha histórica de reposição, sem duplicar o agendador existente.
