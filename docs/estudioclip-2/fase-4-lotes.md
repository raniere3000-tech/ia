# F4.02 — Lotes, reenvio e reposição

Inspeção e testes confirmaram os módulos existentes, sem reescrever o agendador:
`publicacao_lotes` planeja seleção múltipla, prévia, intervalos por destino,
slots, idempotência, pausa/retomada/cancelamento e Retry-After por rede.
A interface Agendar já usa prévia e confirmação; `postagem.postar_agora(pid,
rede)` dirige o reenvio. Redes concluídas e seus links/horários são preservados.

Resultados: publicacao_lotes 12/12, agenda_agente2 45/45 e reposicao 35/35.
A independência entre redes foi validada em F4.01 com 13 verificações.
Todos os envios são locais/simulados; nenhuma conta real usada.

## Duas falhas históricas de reposição

Antes: teste_reposicao 31 PASS/2 FAIL, reproduzindo F1.09. Rastreamento das
funções mostrou que `escolher_vaga` retornava horário a mais de 24 h e
`_pedir_reposicao` corretamente não pedia vídeo. O próprio cenário anterior
havia preenchido a faixa h1 com k3. Marcar todos os cortes como postados não
remove reservas futuras nem significa que há uma vaga no horizonte.

Correção somente no cenário: verificar que o horário ocupado não gera pedido,
então configurar uma faixa efetivamente livre em seis horas, com dia/hora
compatíveis com o relógio do caminho legado. Assert adicional confirma que a
vaga está nas próximas 24 h. Pedido novo e guarda contra repetição passam.
O teste agora tem 35 verificações, incluindo o caso negativo; não foi removida
nenhuma regra de reposição, pausa, orçamento, qualidade ou idempotência.

Não houve alteração de código de produção, flag ou migração. Logs antes,
diagnóstico e depois preservados nos checkpoints. Não afirmar que contas reais
ou Termux foram testados. Próxima: F4.03, inventário de métricas/permissões e
snapshots existentes; número ausente deve continuar ausente.
