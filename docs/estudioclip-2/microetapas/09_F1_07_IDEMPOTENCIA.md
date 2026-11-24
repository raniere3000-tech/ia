# F1.07 — Duplo clique e ações concorrentes

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/fila.py`, `servidor/api_v1.py`, `servidor/aprovacoes.py`, `servidor/thumbnails.py`.

## Execução cirúrgica
1. Reutilizar `fila.enfileirar(chave=...)` e conferir rotas de aprovação, refazer capa, cancelar, liberar.
2. Definir chave estável por ação + projeto + versão + revisão, sem reutilizar em revisões diferentes.
3. Teste de duas solicitações concorrentes; verificar 1 efeito e resposta previsível da segunda.
4. Não criar nova camada de filas.

## Testes focais
Adicionar testes de repetição e concorrência, rodar `teste_thumbnails.py` e `teste_agente3.py` se afetados.

## Aceite / checkpoint
Um clique repetido não produz vídeo/post/capa duplicados; ações de revisões diferentes continuam permitidas.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
