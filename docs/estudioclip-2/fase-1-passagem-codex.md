# EstúdioClip 2.0 — Fase 1: passagem de trabalho (para continuar no Codex)

**Data:** 24/11/2026 11:45 (horário de Brasília)  
**Branch deste trabalho:** `claude/project-thread-hqyqog-fase1` (criado a partir da `main` em `b948059`)  
**Estado:** PARCIAL — trabalho em andamento, **não abrir PR para merge ainda**  
**Documentos de referência:** `00_ARQUITETURA_MESTRE_APROVADA.md`, `02_FASE_1_CONFIABILIDADE_E_ESTADOS.md`, `08_CHECKLIST_REGRESSAO_E_ACEITE.md`, e a auditoria da Fase 0 em `docs/estudioclip-2/fase-0-auditoria-baseline.md` (PR #20, branch `claude/project-thread-hqyqog`).

---

## 1. Ponto de partida (resultado da Fase 0)

- `main` = `b948059` (merge do PR #17). O celular (Termux) está na `main`, no mesmo SHA, com 79 GB livres (conferido pelo dono em 24/11).
- Baseline: 52 arquivos `servidor/testes/teste_*.py` → **43 PASS, 7 FAIL, 2 não automáticos**.
  - FAIL: `teste_agente3`, `teste_central_automacao`, `teste_comandos`, `teste_coordenador`, `teste_descricao`, `teste_liberacao` (os seis começaram no commit `cdda997`, de 22/11, "Revisar cada etapa e refazer o vídeo até o diretor aprovar") e `teste_skills_agentes` (começou em `18b7382`, `KeyError: 'redes'` em `postagem.conferencia`).
  - Não automáticos: `teste_email` (pede dados pelo teclado) e `teste_trecho_link` (precisa de `yt_dlp`).
- Frontend: `npx tsc --noEmit` OK, `npm run build` OK, `npm test` 16/16 OK.
- Como rodar um teste: `cd servidor && PYTHONPATH=. python3 testes/<arquivo>.py` (cada teste cria pasta temporária própria; dá para rodar em paralelo).

## 2. O que já está no branch (não testado por completo)

Diff: `servidor/produtor.py` (+29), `servidor/fila.py` (+15/-3), `servidor/aprovacoes.py` (+2/-2).

### 2.1 Laço infinito do diretor no Agente 3 (causa de `teste_agente3`)
**Achado:** em `produtor.conferir_roteiro`, quando o diretor reprova o roteiro, `corrigir_etapa` manda para `revisar`, que volta para `roteiro`, que reprova de novo… sem limite. Só parava quando estourava o orçamento (`O limite de gasto deste vídeo (R$ 2.00) seria passado`). Confirmado com log: custos `roteiro 0.03` + `correcao 0.03` repetidos até R$ 2,00.

**Feito:**
- `MAX_REPROVACOES_ETAPA` (env, padrão 3) e `_reprovacoes(pid, etapa)` lendo `dados.pareceres_etapas[etapa].reprovacoes` (contador que já existia).
- Em `corrigir_etapa`: passou do limite → evento `etapa_parada_limite`; se a etapa é `pauta`/`roteiro`, põe o projeto em `waiting_brief_approval`, grava `aprovacao_roteiro={'aprovado': False, 'motivo_parada': ...}`, manda o e-mail de roteiro e levanta `fila.Esperar(0, ..., 'aguardando_aprovacao')`. Outras etapas: `ErroProdutor(..., True)` (falha final com mensagem "Precisa da sua revisão").
- Em `conferir_roteiro`: se o roteiro **já foi aprovado por você** e o contador passou do limite, os apontamentos ficam registrados e o fluxo segue (sem novo laço).

### 2.2 Aprovação que chega enquanto a etapa ainda está rodando (corrida)
**Achado:** `aprovacoes.aprovar_roteiro` só liberava jobs em `aguardando_aprovacao`. Se você aprova no instante em que o job ainda está `rodando` (antes de gravar a espera), a aprovação se perde e o job fica parado para sempre. Isso também pode acontecer no fluxo antigo.

**Feito:**
- `fila.liberar(jid)`: se o job está `rodando`, grava `kv['liberar:<jid>']`.
- `fila._executar`, no `except Esperar`: se pedir `aguardando_aprovacao` e existir `liberar:<jid>`, vai direto para `na_fila` e apaga a chave. A chave também é apagada quando a etapa termina sem pedir aprovação, para não valer para uma aprovação futura.
- `aprovar_roteiro` agora libera jobs `agente3.produzir` em `aguardando_aprovacao` **ou** `rodando`.

### 2.3 Ainda falhando (onde parei)
`teste_agente3` agora passa de 10 para 13 verificações ok (roteiro esperando aprovação ✔, trabalho esperando ✔, e-mail ✔). Falha em **"vídeo produzido e pronto para revisão"**: depois de `POST /api/v1/projetos/{PID}/aprovar-roteiro` (resposta 200, job estava `rodando`), o job volta a rodar, mas cai de novo em `etapa_parada_limite` (contador vai de 4 para 5) e `aprovacao_roteiro.aprovado` aparece `False`.

**Hipótese principal:** em `corrigir_etapa`, o `pj.mudar_dados` que grava `aprovado: False` roda **depois** que o teste já viu `waiting_brief_approval` e aprovou, ou na segunda passada sobrescreve a aprovação. Corrigir assim:
1. Na parada, só gravar `aprovado: False` se ainda não estiver `True` (não apagar uma aprovação que já chegou).
2. Gravar o estado do job antes do status do projeto, para que o site/teste não enxergue "esperando você" antes da hora.
3. Conferir com um `print` temporário em `conferir_roteiro` o que `p['dados']['aprovacao_roteiro']` e `_reprovacoes` valem na segunda passada (eu estava fazendo isso quando parei; o print **já foi removido** do código).

## 3. O que falta na Fase 1 (pela especificação 02)

1. **Terminar 2.3** e rodar de novo `teste_agente3`, `teste_central_automacao`, `teste_coordenador`.
2. **6 testes da regra do diretor** (`cdda997`): `aprovacoes.diretor_ok` agora exige `dados.diretor = {sha: <render atual>, veredito: 'aprovado'}` e `qualidade.veredito` sem pendências. A regra foi pedida pelo dono ("refazer até o diretor aprovar"), então o caminho provável é **atualizar os testes** para criar esse parecer. Mas verificar antes se `teste_comandos` (aprovação pelo WhatsApp) e `teste_coordenador` (liberação do pacote) não revelam um fluxo real bloqueado.
3. **`KeyError: 'redes'`**: em `postagem.conferencia` (`postagem.py:1084`), usar `(p.get('redes') or {})` nos dois acessos.
4. **Contrato comum de estados** (`CREATED, QUEUED, RUNNING, WAITING_USER, PAUSED, RETRYABLE_ERROR, CANCEL_REQUESTED, CANCELLED, FAILED, COMPLETED`) como **camada de leitura**, sem trocar os status já salvos. Mapa sugerido a partir de `jobs.status`: `agendado/na_fila→QUEUED`, `rodando`+heartbeat recente→`RUNNING` (heartbeat velho = não é RUNNING), `aguardando_aprovacao→WAITING_USER`, `pausado=1→PAUSED`, `aguardando_tentativa→RETRYABLE_ERROR`, `cancelar=1` ainda rodando→`CANCEL_REQUESTED`, `cancelado→CANCELLED`, `falhou→FAILED`, `concluido→COMPLETED`. A tabela `jobs` já tem `heartbeat`, `iniciado`, `terminado`, `tentativas`, `proxima`, `cancelar`, `chave UNIQUE`. Faltam colunas aditivas (migração 14 em `banco.ESQUEMA`): `source_id`, `video_version_id`, `stage`, `error_code`.
5. **Agente 1 no mesmo vídeo** (`agente.py` ~2026-2031): hoje qualquer erro chama `_marcar_visto(v['id'], 'erro: ...')` e a próxima rodada pega outro vídeo. O job é enfileirado com `max_tentativas=1` (`servidor.py:958`). Fazer: erro recuperável (rede, timeout, 429, FFmpeg transitório) guarda o vídeo como pendente com contador e a próxima rodada tenta **o mesmo** até N vezes com espera crescente; erro de direito, vídeo privado/removido ou URL inválida → `BLOCKED`, sem repetir. Atrás de flag (ex.: `A1_MESMA_FONTE`, **desligada por padrão**).
6. **Cancelar/ignorar em qualquer etapa**: já existe `fila.cancelar/pausar/retomar` e cancelamento cooperativo no FFmpeg (`agente.verificar_cancelamento`, `renderizador.rodar(cancelado=...)`). Falta testar cada etapa (fila, download, corte, IA, render, QA, capa, aprovação, agendamento, coleta) e permitir "ignorar/rejeitar" quem está em `WAITING_USER` sem apagar a auditoria. Testar também depois de reiniciar o servidor.
7. **Duplo toque**: `fila.enfileirar(chave=...)` já é idempotente. Conferir se as rotas de ação (aprovar, refazer capa, cancelar, liberar) passam uma chave, e testar dois pedidos simultâneos.
8. **A6**: rejeitar uma capa sem romper o vínculo da versão aprovada anterior (`thumbnails.py`: hoje há `refazer` e seleção presa ao `video_sha`, mas não há "rejeitar").
9. **Testes novos** para cada item acima, rodar a suíte inteira, PR com o formato exigido e flags desligadas.

## 4. Regras do dono que valem para o Codex

- Uma fase por vez; PR próprio; **nunca fazer merge** sem aprovação dele.
- Não mudar o comportamento atual sem flag (flags começam desligadas). Correção de laço infinito e da corrida de aprovação são consertos de defeito, não funcionalidade nova.
- Não declarar pronto o que não foi testado; o que depende do celular ou de conta real fica "não verificado".
- Nunca rodar testes no celular apontando para `~/.estudioclip` real (os testes usam `DADOS`/`BANCO_ARQ` temporários).

## 5. Prompt sugerido para colar no Codex

> Trabalhe no repositório `raniere3000-tech/ia`, branch `claude/project-thread-hqyqog-fase1`. Leia `docs/estudioclip-2/fase-1-passagem-codex.md` e `docs/estudioclip-2/fase-0-auditoria-baseline.md`, mais os anexos `00_ARQUITETURA_MESTRE_APROVADA.md`, `02_FASE_1_CONFIABILIDADE_E_ESTADOS.md` e `08_CHECKLIST_REGRESSAO_E_ACEITE.md`. Continue a Fase 1 a partir da seção 2.3 (teste_agente3 ainda falha depois da aprovação do roteiro) e depois faça os itens da seção 3 na ordem. Antes de mudar, rode `cd servidor && PYTHONPATH=. python3 testes/teste_agente3.py`. Flags novas desligadas por padrão, migração só aditiva, testes automáticos para cada item. Ao terminar, rode todos os `servidor/testes/teste_*.py` e `cd frontend && npm test && npm run build`, e abra um PR para `main` com o formato: Fase / Branch-base SHA-commit / Estado / Módulos reutilizados / Arquivos alterados / Migrações e backup / Flags / Testes executados / Evidências / Casos não testados / Regressões / Como reverter / Próxima fase liberada?. Não faça merge.
