# F1.03 — Corrigir KeyError de redes sem alterar postagem

**Situação inicial:** PENDENTE. **Escopo máximo:** 10–20 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/postagem.py`, `servidor/testes/teste_skills_agentes.py`.

## Execução cirúrgica
1. Reproduzir `KeyError: redes` em `postagem.conferencia` (~linha 1084 na passagem).
2. Proteger os dois acessos a `redes` com leitura defensiva e validar dados faltantes; não transformar ausência em sucesso de publicação.
3. Acrescentar caso `redes` ausente e parcial; manter comportamento de dados completos.

## Testes focais
```bash
cd servidor && PYTHONPATH=. python3 testes/teste_skills_agentes.py
```

## Aceite / checkpoint
Não existe KeyError; publicação não é realizada sem condições válidas; resultado do teste documentado.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
