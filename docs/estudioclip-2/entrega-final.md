# EstúdioClip 2.0 — entrega para revisão

Implementações F1.01–F5.04 em branches empilhadas e PRs de rascunho, sem merge ou
alteração de produção. Checkpoints por microetapa em docs/estudioclip-2/checkpoints.
A Fase 0 e o patch parcial original foram preservados.

## Ativação autorizada — atualização posterior

Após a entrega, o usuário autorizou ativar todos os recursos. O iniciador
`servidor/iniciar-termux.sh` agora usa 1 para as 11 flags, respeitando valores
explícitos de rollback. A tabela abaixo registra os padrões dos módulos isolados;
o iniciador os sobrepõe. Aplicação no aparelho e limites em ativacao-recursos.md.

## Padrões dos módulos isolados

| Flag | Módulo isolado | Recurso |
| --- | --- | --- |
| A1_MESMA_FONTE | 0 | Retentar a mesma fonte em falhas recuperáveis |
| A1_GANCHO_INTEGRO | 0 | Frase completa na seleção do corte |
| THUMB_REJEICAO | 0 | Recusar proposta de capa |
| A5_EFEITOS_REAIS | 0 | Efeitos comprovados por recibo/SHA |
| RENDER_INTEGRIDADE | 0 | Verificações adicionais no render |
| DNA_CORTE | 0 | Aplicar DNA existente ao corte |
| A3_EDICAO_COMPARTILHADA | 0 | A3 usa o editor existente com recibo e QA |
| FORMATOS_IA | 0 | Três formatos simples de briefing |
| METRICAS_PUBLICACOES | 0 | Snapshots também de publicações IA/manuais |
| PUBLICACAO_CONTEXTO | 0 | Congelar versão/metadados ao publicar em cada rede |
| INTELIGENCIA_METRICAS | 0 | Indicadores e hipóteses de métricas na interface |

Flags são parâmetros do processo do servidor. Nenhuma foi ligada no Termux real.
Correções de defeitos permanecem ativas conforme os módulos existentes. Para a
rastreabilidade dos novos posts é necessário habilitar PUBLICACAO_CONTEXTO antes
do envio; não se reconstrói contexto antigo a partir de arquivos atuais.
METRICAS_PUBLICACOES amplia a captura existente; INTELIGENCIA_METRICAS mostra os
indicadores e habilita o fluxo de hipóteses. Ativar uma flag não concede acesso a
APIs nem substitui autorização da conta.

## Onde revisar

| Fase | Branch | PR |
| --- | --- | --- |
| F1 | claude/project-thread-hqyqog-fase1 | https://github.com/raniere3000-tech/ia/pull/21 |
| F2 | codex/estudioclip-2-fase2 | https://github.com/raniere3000-tech/ia/pull/22 |
| F3 | codex/estudioclip-2-fase3 | https://github.com/raniere3000-tech/ia/pull/24 |
| F4 | codex/estudioclip-2-fase4 | https://github.com/raniere3000-tech/ia/pull/25 |
| F5 | codex/estudioclip-2-fase5 | https://github.com/raniere3000-tech/ia/pull/26 |

## Limites observados

Testes usam contas simuladas e bancos temporários. Não foi validado no celular:
consumo de memória, concorrência de três agentes ou tempo real de render. O teste
de e-mail exige conta e envio reais e fica manual. Métricas TikTok/Kwai e retenção
não têm coletor nesta entrega; ficam indisponíveis. Canal/perfil sem identificação
não é inventado. Testes contextuais são manuais; não fazem distribuição A/B
automática nem alteram DNA ou frequência. Nenhum esquema/tabela novo nesta rodada.

## Rollback

Usar os SHAs e comandos git revert de cada checkpoint, respeitando a ordem das
dependências. Desligar flags preserva auditoria. Hipóteses de métricas podem ser
desativadas ou voltar de versão na Memória; testes associados são encerrados.

## Validação e revisão final

Rodada global no SHA f987561958838f6194ca245e3383a122f4e3a011: **69 arquivos
Python PASS, zero FAIL, um diagnóstico de email interativo excluído**. Inventário
real: 70 arquivos. Isso resolve as quatro falhas históricas da F1.09.

Depois dessa rodada, F5.R01 recebeu sete testes novos e reexecução dos onze grupos
Python afetados (aprendizado, Coordenador, histórico, memória, métricas, feedback,
indicadores, ranking, painel, redes e agenda): todos passaram. Frontend: 18 testes
e build TypeScript/Vite passaram. A suíte global completa não foi repetida após
F5.R01; resultados anteriores e complementares estão separados nos logs.

F5.R01 também distingue o perfil do canal de origem. Quando o publicador recebe
ID da conta/canal no fluxo existente, preserva esse ID por rede, sem consulta
adicional. Ausência fica indisponível. Recibos IA são encontrados no render
original pelo SHA, mesmo quando o arquivo da fila é uma cópia. Roteiro vem de
versão arquivada que corresponda ao render, com hash de aprovação válido; nunca
da versão atual editada depois. Política e certificado QA são vinculados ao SHA.
Reposts do mesmo render não contam como vídeos distintos nas amostras inferenciais.

Evidências: regressao-global.md, checkpoints/REGRESSAO_FINAL-suite e F5.R01-*.log.
Checkpoint definitivo e próximo passo em ESTADO_ATUAL.md. PRs continuam em rascunho.
