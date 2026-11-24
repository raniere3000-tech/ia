# EstúdioClip 2.0 — continuação enxuta e retomável

**Objetivo:** completar apenas as melhorias necessárias, utilizando o que já existe, a partir da Fase 0 concluída e da Fase 1 parcialmente iniciada. Este pacote NÃO autoriza refatoração geral, nem merge em produção.

## Origem verificada
- Entrega do usuário `fase-1-passagem-codex.md`, datada de 24/11/2026 11:45; patch `fase1-em-andamento.diff`.
- Fase 0: auditoria documentada em `docs/estudioclip-2/fase-0-auditoria-baseline.md` (PR #20, segundo a passagem). `main` registrado na passagem como `b948059`. Não assumir que ainda seja o SHA atual.
- Branch de continuidade: `claude/project-thread-hqyqog-fase1`. Na consulta deste pacote, o branch existia no GitHub em `ca2652614dd453f7cdcf2e9d9320436ba596efd7`. **Confirmar HEAD e diff antes de editar.**
- Baseline informado: 52 testes Python: 43 PASS, 7 FAIL, 2 interativos/dependentes de ambiente. Frontend: TypeScript e build aprovados, testes 16/16.
- Em andamento: `servidor/produtor.py`, `servidor/fila.py`, `servidor/aprovacoes.py`; ver `01_ESTADO_REAL_E_NAO_REFAZER.md`.

## Como executar
1. Leia `01_ESTADO_REAL_E_NAO_REFAZER.md`, `02_PROTOCOLO_RETOMADA.md` e o cartão de microetapa indicado em `ESTADO_ATUAL.md`.
2. **Execute somente uma microetapa por sessão**, com limite de escopo e teste local delimitado; se houver pouco tempo/cota restante, atualize checkpoint e PARE antes de iniciar outra.
3. Ao fim de cada microetapa: teste focal, salve o checkpoint, commit isolado na branch de trabalho, anote SHA e próxima ação. Nunca afirmar que o commit foi feito sem obter o SHA.
4. A bateria completa (incluindo os 52 testes e frontend) acontece no fecho da fase; microetapas usam testes focados para não gastar toda a cota.
5. PR por fase, merge **somente com autorização do dono**. Não enviar mudanças para `main` automaticamente.

## Arquivos e ordem
- `03_F1_01_CORRIDA_APROVACAO.md` → `04_F1_02_REGRA_DIRETOR.md` → `05_F1_03_ERRO_REDES.md` → `06_F1_04_ESTADOS_LEITURA.md` → `07_F1_05_REPETIR_FONTE_A1.md` → `08_F1_06_CANCELAR_IGNORAR.md` → `09_F1_07_IDEMPOTENCIA.md` → `10_F1_08_THUMB_REJEITAR.md` → `11_F1_09_FECHAMENTO.md`.
- Depois: `12_F2_CORTES_EDICAO_INCREMENTAL.md`, `13_F3_CRIACAO_IA_INCREMENTAL.md`, `14_F4_PUBLICACOES_METRICAS.md`, `15_F5_INTELIGENCIA_APRENDIZADO.md`.
- `16_CHECKLIST_MINIMO.md`, `17_PROMPT_COPIAR_CODEX.md`, `ESTADO_ATUAL.md`.

**Regra de ouro:** não criar serviço/agent/banco novo se um módulo existente já resolver. Medir, corrigir e integrar.
