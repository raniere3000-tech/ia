# F1.01 — Concluir aprovação de roteiro A3 sem perder estado

**Situação inicial:** EM ANDAMENTO (passagem Codex 24/11). **Escopo máximo:** 20–40 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/produtor.py`, `servidor/fila.py`, `servidor/aprovacoes.py`, `servidor/testes/teste_agente3.py`.

## Execução cirúrgica
1. Confirmar no branch `claude/project-thread-hqyqog-fase1` se o patch enviado já está aplicado; não aplicar diff cegamente.
2. Reproduzir falha: 13 checkpoints passam, depois volta a `etapa_parada_limite`; aprovação `True` é sobrescrita por `False`.
3. Localizar a escrita concorrente no `pj.mudar_dados`, preferindo atualização condicional/atômica que nunca retrocede uma aprovação válida da revisão correta. Verificar ordem da visibilidade `waiting_brief_approval` e `aguardando_aprovacao`.
4. Garantir que marcador `liberar:<jid>` seja consumido somente na geração/etapa correta; impedir sinal antigo de liberar nova aprovação.
5. Não permitir bypass para nova revisão de roteiro que não tenha sido explicitamente aprovada.
6. Adicionar teste de corrida (aprovação enquanto `rodando`) e de retomada após reinício usando banco temporário.

## Testes focais
```bash
cd servidor && PYTHONPATH=. python3 testes/teste_agente3.py
```
Rodar também o teste novo que reproduz a corrida e, se concluído, `teste_central_automacao.py` e `teste_coordenador.py`.

## Aceite / checkpoint
Vídeo segue até revisão depois da aprovação do usuário; aprovação não regride; máximo de reprovações interrompe laço; não exige orçamento infinito; nenhuma aprovação futura é antecipada.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
