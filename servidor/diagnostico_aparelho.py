"""Diagnóstico do celular sem precisar ligar o servidor.

No Termux:   cd ~/ia/servidor && python diagnostico_aparelho.py
             (ou: bash iniciar-termux.sh diagnostico)
Só a ficha:  python diagnostico_aparelho.py --rapido

Grava o laudo em ~/estudioclip-diagnostico.json e o registro em ~/estudioclip-diagnostico.log.
Não instala nada: no fim mostra o comando com o que falta, para você rodar se quiser.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hardware  # noqa: E402


def _mb(v):
    return '?' if v is None else f'{v} MB'


def main():
    rapido = '--rapido' in sys.argv
    casa = Path.home()
    f = hardware.ficha()
    p, m, ff = f['processador'], f['memoria'] or {}, f['ffmpeg']
    print('== EstúdioClip: diagnóstico do aparelho ==')
    print('Onde rodou:', f['ambiente'])
    if f['android']:
        a = f['android']
        print(f"Android {a['versao'] or '?'} (SDK {a['sdk'] or '?'}) • {a['aparelho'] or 'aparelho ?'} • Termux {a['termux'] or '?'}")
    print(f"Processador: {p['arquitetura']} • {p['modelo'] or 'modelo ?'} • {p['nucleos']} núcleos • até {p['mhz_max'] or '?'} MHz")
    print(f"Memória: {_mb(m.get('total_mb'))} no total, {_mb(m.get('livre_mb'))} livres • Espaço livre: {_mb(f['espaco']['livre_mb'])}")
    print(f"Python {f['python']} • Node {f['node'] or 'não tem'} • {f['git'] or 'git não tem'}")
    if ff.get('instalado'):
        print('FFmpeg', ff['versao'])
        if ff['faltam_codificadores']:
            print('  Faltam codificadores:', ', '.join(ff['faltam_codificadores']))
        if ff['faltam_filtros']:
            print('  Faltam filtros:', ', '.join(ff['faltam_filtros']))
    else:
        print('FFmpeg: NÃO instalado')
    pk = f['pacotes']
    for i in pk['itens']:
        print(f"  [{'ok' if i['tem'] else '--'}] {i['pacote']:<14} {i['importancia']:<12} {i['para']}")
    if pk['comando']:
        print('\nFalta o necessário. Rode:\n  ' + pk['comando'])
    if pk['comando_opcional']:
        print('Opcional (só se for usar):\n  ' + pk['comando_opcional'])
    if rapido:
        (casa / 'estudioclip-diagnostico.json').write_text(json.dumps({'ficha': f}, ensure_ascii=False, indent=1), encoding='utf-8')
        print('\nFicha gravada em ~/estudioclip-diagnostico.json')
        return 0
    if not ff.get('instalado'):
        print('\nSem FFmpeg não dá para testar o render. Instale e rode de novo.')
        return 1
    print('\nTestando o render (uns minutos; pode deixar a tela ligada)...')
    pasta = casa / '.estudioclip' / 'diagnostico'
    t0 = time.time()
    laudo = hardware.testar(pasta, log=print)
    for t in laudo['testes']:
        if not t.get('ok'):
            print(f"  {t['titulo']}: PROBLEMA -> {t.get('erro') or t.get('conferencia', {}).get('erros') or t.get('reproducao', {}).get('erros')}")
    (casa / 'estudioclip-diagnostico.json').write_text(json.dumps(laudo, ensure_ascii=False, indent=1), encoding='utf-8')
    (casa / 'estudioclip-diagnostico.log').write_text('\n'.join(laudo['log']) + '\n', encoding='utf-8')
    print(f"\nPronto em {time.time() - t0:.0f} s. Estado: {laudo['estado']}.")
    print('Laudo: ~/estudioclip-diagnostico.json   Registro: ~/estudioclip-diagnostico.log')
    print('Mande o arquivo ~/estudioclip-diagnostico.json (ou um print desta tela) para o Claude.')
    return 0 if laudo['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
