# F4.04 — histórico por versão

`PUBLICACAO_CONTEXTO=0` mantém o recurso aditivo desligado por padrão. Quando
ligado, antes do envio é congelado o contexto local: SHA256 do arquivo, projeto,
origem, corte/canal conhecidos, título/legenda, gancho/template registrados,
recibo de efeitos apenas se vinculado ao SHA real e seleção de capa válida.
Não se afirma que a rede aceitou uma capa apenas por ela estar selecionada.

Após sucesso, o contexto é salvo no destino existente com rede, ref/ID, link e
instante real. Falhas não geram histórico de sucesso. O YouTube passa a preservar
seu ID retornado também em ref. Cada rede mantém seu próprio contexto. Legados
não recebem contexto reconstruído de uma versão atual.

Snapshots existentes recebem esse contexto no campo reservado `_publicacao` do
JSON de variáveis. Nenhuma tabela nova. Comparações de aprendizado continuam
restritas às variáveis conhecidas. Alterar arquivo, gancho ou título depois não
reescreve publicação anterior nem snapshot persistido.

Validação: quatro testes novos (sucesso, edição posterior, recibo/legado, falha),
sete testes de métricas, redes independentes 13, aprendizado 47 e painel 34.
Agendamento integra o fecho da fase. Tudo com contas simuladas.
