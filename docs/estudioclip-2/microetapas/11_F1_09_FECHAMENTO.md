# F1.09 — Fechar Fase 1 com regressão e PR

**Situação inicial:** PENDENTE. **Escopo máximo:** 30–80 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/testes/`, `frontend/`, `docs/estudioclip-2/`.

## Execução cirúrgica
1. Revisar checkpoints F1.01–F1.08 e conferir que todos têm commit e teste focal.
2. Executar novamente os 52 testes Python de baseline com ambiente isolado; identificar test_email/yt_dlp como não automáticos conforme caso. Não esconder falhas já conhecidas.
3. `cd frontend && npx tsc --noEmit && npm test && npm run build`.
4. Comparar contra Fase 0: 43 PASS, 7 FAIL, 2 não automáticos e 16 testes frontend; documentar diferença e razões.
5. Produzir relatório resumido por defeito, evidência, flags, rollback e teste no Termux ainda pendente.
6. Abrir PR para `main` **sem fazer merge**; testar comportamento no celular somente em ambiente de teste e com autorização.

## Testes focais
Suite completa Python, testes frontend e build, resultado com stdout/stderr e data em `docs/estudioclip-2/checkpoints/`.

## Aceite / checkpoint
Nenhuma regressão nova; 7 falhas iniciais resolvidas ou explicitamente bloqueadas com justificativa; PR revisável, sem merge.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
