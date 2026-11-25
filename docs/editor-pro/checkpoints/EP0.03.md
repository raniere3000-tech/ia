# EP0.03 — Baseline local de render e recursos

Status: APROVADA para o baseline Linux. Android físico: PENDENTE_TERMUX, previsto em EP6.02.

- Ambiente x86_64, FFmpeg e ffprobe 7.1.5, cerca de 16 GiB livres em disco e 9,7 GiB de RAM. Pico agregado reportado por `RUSAGE_CHILDREN`: 662844 KiB. Esse pico é o maior observado entre os processos testados no Linux.
- `teste_efeitos_reais.py`: 6/6, 5,673 s. A diferença média RGB do zoom foi 0,00 antes, 73,39 durante e 3,85 depois. O arquivo passou por comparação de quadros, com B-roll licenciado, legenda visível, fade e hash de recibo.
- `teste_integridade_render.py`: 7/7, 7,669 s. Fixtures com preto, imagem congelada, conteúdo escuro intencional e mídia normal. Falha preservou o arquivo anterior.
- `teste_a3_editor_compartilhado.py`: 9/9, 12,447 s. Montagem original, recibo do A5, contexto de publicação e cenários de bloqueio.
- `teste_portao_diretor.py`: 15/15. `teste_memoria_metricas.py`: 5/5.
- `PYTHONPATH=servidor python servidor/testes/teste_skills.py` e `teste_skills_agentes.py`: 57 e 24 verificações, zero falhas. A primeira chamada sem PYTHONPATH não encontrou o módulo banco. A execução válida usou PYTHONPATH.
- Nenhum acesso autorizado ao aparelho foi disponibilizado nesta sessão. A execução local usou mídia sintética e integrações de teste.
- Sem mudanças de runtime. Reversão: reverter o commit documental. Próxima tarefa: EP1.01, auditoria dos oito candidatos.
