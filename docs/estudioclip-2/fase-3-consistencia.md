# F3.02 — Consistência visual por projeto

Reutilizados os snapshots existentes de `series.foto_da_serie`,
`criativo.foto_avulsa` e `produtor.preparar_cena`. Não foi criado banco,
serviço ou formato paralelo de identidade. Nenhuma migração ou flag nova.

A biblioteca pode avançar para a versão 2 enquanto o episódio conserva a 1.
O aviso correspondente agora fica resolvido somente se o snapshot coincide
com os dados da versão fixada em `personagens_versoes`. A evidência registra
ID, versão e hash. Não se adota a versão nova silenciosamente nem se exige
renderizar o episódio com outra roupa ou voz.

Snapshot divergente da versão histórica continua bloqueado. Histórico ausente
não recebe exceção. Voz incorreta, personagem que fala fora do elenco, cenário
inválido e contradição com fato aprovado continuam como pendências abertas.
As regras de qualidade e certificado final permanecem em vigor.

Seis testes focais: snapshots antes/depois, duas cenas renderizadas antes e
depois de mudanças de roupa/voz/cenário, novo episódio com versão nova,
adulteração do snapshot, histórico ausente, voz/elenco/cenário inválidos e
contradição real com a bíblia. Nos seis renders reais, os dois clipes do
projeto original conservam seus SHAs após a mudança da biblioteca; o episódio
novo usa a identidade nova. Voz sintética local de teste; nenhuma API real.
Regressões correlatas: criativo, série completa e diretor aprovadas.

O integral de agente3 continua pendente de F3.03: a opinião visual falsa usada
pelo simulador bloqueia o final, e o simulador de continuidade inventa uma
contradição até para falas que não a contêm. Seu caso negativo deve continuar
coberto (há um teste focal específico), separado de histórias consistentes.
Não afirmar aprovação integral de Fase 3 ou Termux.
