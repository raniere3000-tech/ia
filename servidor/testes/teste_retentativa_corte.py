"""Reproduz falha parcial e confere que a fila retenta o vídeo original."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory(prefix='ec-retentativa-') as pasta:
    os.environ['DADOS'] = pasta
    os.environ['BANCO_ARQ'] = str(Path(pasta) / 'teste.sqlite')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    import agente as ag
    import banco as db
    import fila
    import servidor

    db.migrar()
    ag.salvar_config({'cortes': {'por_video': 2, 'por_analise': 0}})
    fila.registrar('agente1.pesado', servidor._job_agente1, 'pesado')

    video = {'id': 'abcdefghijk', 'titulo': 'Primeiro vídeo', 'canal': 'canal', 'canal_nome': 'Canal'}
    pedidos = []

    def processar(v, quantos, *, extra, pre):
        pedidos.append((v['id'], extra['corte_lote'], quantos))
        n = len(pedidos)
        c = {**extra, 'id': f'c{n}', 'status': 'pronto', 'ini': n * 10, 'fim': n * 10 + 8}
        ag._mudar(lambda e: e['cortes'].append(c))
        if n == 1:
            raise OSError('FFmpeg interrompido no segundo corte')
        return [c]

    with patch.object(ag, 'proximo_video', return_value=video) as busca, patch.object(ag, 'processar_video', side_effect=processar), \
         patch.object(ag, 'avisar'), patch.object(ag, 'email_corte', return_value=False), patch.object(ag, 'depois_do_trabalho'):
        jid = servidor._enfileirar_agente1('cortar')['job']
        fila._executar(fila.obter(jid))
        esperando = fila.obter(jid)
        assert esperando['status'] == 'aguardando_tentativa'
        assert esperando['proxima'] > 0 and 'FFmpeg interrompido' in esperando['etapa']
        assert video['id'] not in ag.estado()['vistos']
        assert servidor._enfileirar_agente1('cortar')['job'] == jid

        fila.tentar_de_novo(jid)
        fila._executar(fila.obter(jid))
        pronto = fila.obter(jid)
        assert pronto['status'] == 'concluido'
        assert '2 corte(s)' in json.loads(pronto['resultado'])['mensagem']
        assert busca.call_count == 1 and pedidos[0] == pedidos[1]
        assert len(ag.estado()['cortes']) == 2 and not ag.estado()['cortes_pendentes']
        assert video['id'] in ag.estado()['vistos']

print('OK: retentativa usa a mesma fonte e preserva o corte já salvo.')
