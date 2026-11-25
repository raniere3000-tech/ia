# F5.01 — indicadores filtrados

A área existente Agentes → Aprendizado recebe indicadores por vertente, rede,
canal e período da medição. Reutiliza aprendizado_snapshots; a consulta não
coleta nem grava dados. Não foi criada memória ou tabela paralela.

Cada publicação/rede/versão usa a última observação disponível dentro do período,
evita somar contagens cumulativas e mostra cobertura por métrica. Ausência fica
Indisponível; zero medido continua zero. Retenção permanece indisponível.
Legados sem contexto conservam origem indisponível, sem inferir versão/canal.
Canal sem informação não entra num filtro específico.

Quatro testes cobrem deduplicação, filtros combinados, ausência/zero/legado e
consulta sem HTTP. Frontend: 18 testes e build TypeScript/Vite passaram.
