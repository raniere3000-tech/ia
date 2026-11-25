# Fase 1 — flags e limites

Ambas as funcionalidades novas começam desligadas. Nenhuma configuração de produção
foi alterada nesta entrega. As demais alterações são correções de defeitos.

| Variável de ambiente do servidor | Padrão | Efeito |
| --- | --- | --- |
| A1_MESMA_FONTE | 0 | Repetir fonte em falhas transitórias, com estado persistente |
| A1_FONTE_MAX_TENTATIVAS | 3 | Limite total por fonte; ajustado entre 1 e 10; só com a flag ativa |
| THUMB_REJEICAO | 0 | Habilitar API e botão Recusar nas propostas de capa |

Em ambiente de teste, iniciar o servidor com as variáveis desejadas definidas no
processo. Por exemplo, `A1_MESMA_FONTE=1 THUMB_REJEICAO=1 python3 servidor.py` a partir
da pasta servidor. Desligar a flag não apaga os registros já criados.

A1 usa 60s, 180s, 540s de espera crescente (teto 1800s), sem trocar de fonte dentro
da sequência. URLs inválidas, fonte privada/removida, permissão revogada e teto de
custo não são repetidos automaticamente. A rotina atual de banco de trechos não foi
substituída. O limite de reprovações do Diretor introduzido antes desta retomada
continua em MAX_REPROVACOES_ETAPA (padrão 3).

Recusar capa não gera substituta nem remove a seleção aprovada. A variante rejeitada
permanece auditável no histórico. Uma capa escolhida exige substituta válida antes
de recusar aquela versão. Não há alteração de esquema ou migração nesta fase.
