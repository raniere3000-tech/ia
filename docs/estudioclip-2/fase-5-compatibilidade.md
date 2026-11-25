# F5.R01 — compatibilidade e qualidade dos dados

Revisão complementar às microetapas: INTELIGENCIA_METRICAS=0 oculta os indicadores
e desliga propostas/testes de métricas por padrão; as rotinas de aprendizado
anteriores continuam funcionando. Não altera configuração de produção.

Capturas de cortes legados sem data da leitura não usam a data de postagem como
se fosse medição. Canal fonte fica em canal_origem. Perfil/versão do canal usa
os valores preservados no corte; ID da conta retornado pelo fluxo de publicação
pode identificar o canal da rede quando não há perfil. Não faz nova consulta OAuth
nem presume permissão de métricas. Metadados ausentes permanecem indisponíveis.

O arquivo copiado para a fila IA recupera recibo do render original, validando
status concluído e SHA; roteiro somente de versão arquivada ligada ao render e
aprovação correspondente. O certificado válido e a política são congelados no
histórico. Editar o projeto depois não muda esse vínculo. A interface mostra
versão/roteiro e permite quebrar linhas de hashes em telas pequenas.

Hipóteses e testes contextuais contam renders distintos: várias postagens do
mesmo arquivo não completam artificialmente o mínimo de vídeos.

Sete testes novos e onze grupos afetados passaram. Frontend 18 testes e build
passaram. A rodada global anterior teve 69 arquivos PASS; esta é a evidência
complementar posterior, sem alegar nova execução global integral.
