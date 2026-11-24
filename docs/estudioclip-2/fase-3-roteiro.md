# F3.01 — Roteiro e aprovação

A correção de produção da F1.01 foi preservada; nenhum módulo do aplicativo
foi alterado nesta microetapa. O teste integrado agora distingue o revisor
sempre negativo do primeiro cenário (aceite explícito necessário) dos cenários
posteriores com roteiro válido. Não desliga o Diretor nem altera a nota mínima.

O cenário focal cria roteiro, para sem renderizar, recebe revisão do texto,
recusa aprovação com revisão antiga (409), aceita a revisão atual e continua
no mesmo job até H.264/AAC 1080x1920 com SHA conferido, sem criar post. Os
apontamentos aceitos ficam auditáveis com hash. Resultado final: 23 aprovados;
concorrência/retomada de aprovação: 10 aprovados. Flags/migrações: nenhuma.

O teste de planos passou a verificar os segmentos reais no disco, aceitando
cache: exigir `refeito=true` em todos os segmentos contradizia a retomada.
Esperas de produção passam a falhar no primeiro bloqueio com o diagnóstico,
em vez de continuar e produzir KeyError sobre render/imagem inexistente.

## Integral continua bloqueado

A execução integral retomada terminou com exit 1: oito asserções falharam e
houve uma exceção ao acessar render inexistente. Essa execução foi anterior à
melhoria final de diagnóstico/cache; seu log completo permanece preservado.
Não declarar teste_agente3 integral ou Fase 3 aprovados.

Causas observadas nos jobs SQLite temporários:

- Planos: quatro correções de final por `IA (opinião): Rosto cortado na borda`,
  sem produzir render aprovado. Os segmentos reais existem. Tratar a política
  de julgamentos/QA compartilhado em F3.03, mantendo bloqueios objetivos.
- Série: render reprova por `Ana mudou de aparência (versão 1 para 2)` embora
  o próprio parecer confirme que o episódio conserva a versão 1. Conferir
  consistência real do snapshot, vozes e cenários na F3.02; não trocar o
  episódio silenciosamente pela aparência nova.
- O simulador de continuidade também sempre inventa uma contradição. Separar
  casos de sucesso e contradição real em testes de consistência, preservando
  um caso negativo que bloqueia a produção.

Não há evidência de defeito no render por planos no ambiente retomado: testes
isolados 160x284 e 1080x1920 produziram duração correta. O log anterior foi
interrompido nesse ponto; não deve ser apresentado como teste aprovado.
