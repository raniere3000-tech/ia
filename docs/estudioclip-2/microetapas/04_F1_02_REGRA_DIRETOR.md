# F1.02 — Verificar regra de aprovação do Diretor sem maquiar testes

**Situação inicial:** PENDENTE. **Escopo máximo:** 15–35 min estimados, sujeito a ambiente; trabalhar somente neste cartão.

**Arquivos prioritários:** `servidor/aprovacoes.py`, `servidor/diretor.py`, `servidor/qualidade.py`, testes de liberação/coordenador/comandos.

## Execução cirúrgica
1. Reproduzir os seis testes de baseline associados à mudança `cdda997`.
2. Verificar requisito `dados.diretor = {sha:<render_atual>, veredito:"aprovado"}` e `qualidade.veredito`; não permitir certificado de render antigo.
3. Classificar cada falha como fixture de teste obsoleto **ou** fluxo de produção bloqueado.
4. Corrigir código se fluxo real estiver errado. Atualizar fixture só quando reproduzir realisticamente parecer legítimo, sem remover portão de qualidade.
5. Testar aprovação, rejeição, render alterado e comando remoto.

## Testes focais
Testes focais: `teste_comandos.py`, `teste_coordenador.py`, `teste_descricao.py`, `teste_liberacao.py`, `teste_central_automacao.py` (rodar os que dependem diretamente do ajuste).

## Aceite / checkpoint
Nenhum vídeo sem certificado válido é liberado; testes passam por comportamento real, não por afrouxamento de critérios.

Antes de iniciar a próxima microetapa: atualizar `ESTADO_ATUAL.md`, registrar commit e SHA, deixar o ambiente retomável conforme `02_PROTOCOLO_RETOMADA.md`. Não fazer merge.
