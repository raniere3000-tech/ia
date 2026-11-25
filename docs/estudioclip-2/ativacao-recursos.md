# Ativação autorizada dos recursos 2.0

O usuário pediu para ativar todos os recursos em 24/11/2026 (horário de Brasília).
`servidor/iniciar-termux.sh` agora exporta os 11 recursos novos com valor 1, tanto
no início normal como no modo link e nos processos reiniciados pelo vigia.
O modo Termux:Boot chama o mesmo iniciador e herda essa configuração.

Recursos: A1_MESMA_FONTE, A1_GANCHO_INTEGRO, THUMB_REJEICAO, A5_EFEITOS_REAIS,
RENDER_INTEGRIDADE, DNA_CORTE, A3_EDICAO_COMPARTILHADA, FORMATOS_IA,
METRICAS_PUBLICACOES, PUBLICACAO_CONTEXTO e INTELIGENCIA_METRICAS.

Um valor 0 definido explicitamente no ambiente vence o padrão 1 do iniciador.
Exemplo de rollback pontual: `RENDER_INTEGRIDADE=0 bash iniciar-termux.sh link`.
Importar módulos Python isoladamente continua com os padrões anteriores; quem
inicia com `python servidor.py` diretamente deve exportar as mesmas variáveis.
A mudança está no iniciador usado no celular, sem duplicar carregadores de configuração.

## Aplicar no aparelho

É preciso ter a branch `codex/estudioclip-2-fase5` atualizada no celular e executar,
a partir da pasta servidor:

```bash
bash iniciar-termux.sh link
```

O iniciador existente reinicia o servidor anterior. Não foi executado no celular
nesta sessão. O site publicado ainda usa main; recursos de interface também
precisam da versão correspondente do frontend. Nenhum PR foi integrado ou site
publicado nesta alteração. A main observada está em b8d1329, com PR23 de outro
trabalho; essa alteração concorrente não foi sobrescrita nem incorporada por merge.

Ativar recursos não concede permissões de API nem aprova o aplicativo TikTok.
Métricas não fornecidas continuam indisponíveis. Aprovações de vídeo, direitos,
certificado QA, regras de agendamento e credenciais existentes foram preservados.

## Validação

`bash -n servidor/iniciar-termux.sh` passou. Três testes executam o iniciador real
em cópia temporária, com rede, instalador, pkill e processo de servidor substituídos;
verificam herança dos 11 recursos, rollback explícito e leitura pelos módulos.
Com os 11 recursos no ambiente, edição compartilhada passou em 9 testes,
integridade do render em 7 e compatibilidade/métricas em 7 (os testes preservam
seus casos explícitos de flag desligada). Sem APIs/contas reais.

## Atualizar o celular com um comando

```bash
bash ~/ia/servidor/atualizar-termux.sh
```

Faz: wake lock, para servidor/túnel/vigia, atualiza o cloudflared, `git checkout main`,
`git pull --ff-only` e `bash iniciar-termux.sh link`. Se o pull falhar por mudanças
locais, o script para e avisa em vez de iniciar uma versão velha.
