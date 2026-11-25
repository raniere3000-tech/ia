# F1.08 — Rejeitar thumbnail sem perder a anterior

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/thumbnails.py`, `servidor/aprovacoes.py`, `frontend/src/pages/Thumbnails.tsx` (confirmar caminho).

## Execução cirúrgica
1. Reutilizar fluxo existente de refazer/selecionar e vínculo a `video_sha`.
2. Permitir rejeitar proposta de capa explicitamente; preservar capa aprovada da versão atual até substituta validada.
3. Não gerar capa nova só porque outro estágio foi reprocessado sem mudança visual relevante.
4. Testar rejeição, nova proposta, seleção e vínculo ao render atual; flag se mudança de comportamento.

## Testes focais
`teste_thumbnails.py`, `teste_versao_refeita.py` e testes de interface existentes se forem tocados.

## Aceite / checkpoint
A6 permite rejeitar; capa aprovada não some; capa de render antigo não vai para publicação.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
