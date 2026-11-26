# F5.04 — hipótese, aprovação e teste versionados

Reutiliza coordenador_memorias, suas versões/evidências e aprendizado_experimentos.
A hipótese de métricas registra amostra/snapshots, responsável, canal, rede,
vertente, variável e alternativas A/B. Nasce como proposta; confirmar e iniciar
um teste são ações explícitas na tela de Memória. Não cria agente ou tabela nova.

Confirmação/CAS, registro do experimento e versão da memória são transacionais;
repetir com a versão atual retorna o mesmo teste. O experimento permanece manual:
distribuir A/B e manter os demais fatores fixos; não há alteração automática dos
agentes, prompts, DNA, agendamento ou autorização de postagem.

A amostra do teste exige publicações posteriores à sua criação no canal, vertente
e rede escolhidos. A amostra histórica da hipótese não conta como resultado.
O mínimo existente continua obrigatório. Encerrar congela o resultado. Desativar
ou reverter a memória encerra o teste vinculado quando necessário. Versões e
aprovações permanecem no histórico; hipóteses de canal/vertente não se aplicam
fora de seu contexto. Não há escrita no arquivo de perfis/DNA.

UI: Coordenador → Aprendizado → Propor como memória; Memória → Confirmar →
Iniciar teste controlado. Acompanhamento em Agentes → Aprendizado. Desativar ou
voltar de versão usa os controles de memória existentes.

Cinco testes novos cobrem autorização, transação/CAS, isolamento, amostra nova e
rollback; aprendizado 47, Coordenador 80, painel 34 e demais testes de indicadores,
ranking/feedback passaram. Frontend 18 e TypeScript/Vite passaram. Ainda falta
regressão global, Termux e verificação com contas reais.
