# F3.03 — Montagem e efeitos compartilhados

`A3_EDICAO_COMPARTILHADA=0` por padrão. Com `1`, a montagem original segue
pelo EditPlan e `editor_ia.executar_importado` existentes, com comprovação de
efeitos e passagem pelo A4 existente antes/depois da edição. O padrão aplica
fade curto de 120ms; o plano em `dados.plano_edicao` pode usar efeitos tipados
já disponíveis. Não foi criado editor, agente, banco ou migração.

A finalização mantém um único trecho completo e o formato do storyboard.
Alterações de duração ficam nas cenas para preservar voz e SRT. A duração
usa o relógio do vídeo; padding AAC do contêiner não deve cortar fala ou fazer
um plano completo parecer incompleto. Enquadramento mantido é registrado como
sem alteração, não como efeito aplicado. B-roll continua sujeito à flag e
validações próprias já existentes.

O mesmo executor aceita `comprovar=True` e callback de cancelamento. O recibo
contém hash do plano, SHA do arquivo, fonte, planejados/aplicados/sem alteração/
falhas e parâmetros. É guardado atomicamente no projeto, na execução existente
do pipeline e como arquivo JSON ao lado do render, também registrado como asset.
SHA/plano divergentes não liberam a montagem. Falha/cancelamento preservam a
saída anterior. A4 continua exigindo arquivo válido, nota e certificado por SHA;
nenhum post é criado nesta etapa.

## Testes e política do Diretor

Nove testes focais com FFmpeg e A4 reais: história narrada, curiosidade com
zoom pontual medido por frames, certificado por SHA, opinião pendente bloqueada,
filtro real de confiança da visão, falha de efeito, recibo falso, cancelamento,
restrição de timeline e flag desligada (alguns casos combinam verificações).
Regressões: efeitos 6, integridade 7, portão de aprovação 15, pipeline 51 e
`teste_diretor` aprovados. `teste_agente3` integral: **176 ok, zero falhas**.

A investigação corrigiu a interpretação do checkpoint anterior: o contrato
atual testado pelo Diretor bloqueia opinião pendente. Essa regra foi preservada.
O simulador integral antigo devolvia defeito visual/contradição para todo caso,
mas esperava sucesso. Os cenários positivos agora retornam avaliação válida;
casos negativos continuam cobertos no teste compartilhado, Diretor e nos seis
testes de consistência (incluindo contradição real da bíblia). Nenhum gate,
nota mínima ou certificado foi relaxado para tornar a suíte verde.

Não há frontend alterado nesta microetapa. Termux e provedores/contas reais
não foram executados. O sucesso integral do teste não representa aceite de
produção de todas as fases. Sem merge/deploy.
