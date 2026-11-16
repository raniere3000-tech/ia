"""Demonstração real de cada estilo que roda no celular (etapa T5): 5 s por estilo e por efeito de cena,
com tempo medido, conferência técnica (preto, congelado, som, decodificação) e uma folha com um quadro de cada.

Uso: python testes/gerar_demos.py [pasta] [--leve]
O resultado diz onde foi medido: fora do Android o tempo NÃO vale para o celular.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import estilos_codigo as ec  # noqa: E402
import hardware  # noqa: E402
import renderizador as rd  # noqa: E402


def main():
    leve = '--leve' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    base = Path(args[0]) if args else Path.home() / 'estudioclip-demos'
    base.mkdir(parents=True, exist_ok=True)
    W, H = (540, 960) if leve else ec.FORMATOS['9:16']
    itens = [(e['id'], '') for e in ec.catalogo() if e['servidor'] and not e['precisa_imagem']]
    itens += [('animado2d', v) for v in ec.VARIANTES_DEMO]
    out = []
    for eid, var in itens:
        nome = eid + (f'-{var}' if var else '')
        pasta = base / nome
        pasta.mkdir(exist_ok=True)
        saida = pasta / 'demo.mp4'
        cena = ec.demo_cena(eid, var)
        audio = None
        if eid in ec.ANIMADOS:
            audio = pasta / 'fala.wav'
            rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                      "aevalsrc='0.6*sin(2*PI*(220+180*sin(2*PI*0.7*t))*t)*max(0,sin(2*PI*3.3*t))*lt(mod(t,1.6),1.2)':s=24000:d=5",
                      '-ac', '1', '-c:a', 'pcm_s16le', str(audio)], tempo_max=60)
            cena['_audio'] = str(audio)
        t0 = time.time()
        try:
            ec.preparar(eid, W, H, 5.0, None, None, cena=cena)
            rd.rodar(ec.montar(eid, cena, W, H, 5.0, pasta, None, audio, saida), tempo_max=1800)
            conf = rd.conferir(saida, pasta, {'largura': W, 'altura': H, 'duracao': 5.0})
            r = {'estilo': eid, 'efeito': var, 'ok': conf['ok'], 'segundos': round(time.time() - t0, 1), 'erros': conf['erros'], 'avisos': conf['avisos'],
                 'tecnologia': ec.TECNOLOGIA.get(eid, ('', ''))[0], 'limites': ec.TECNOLOGIA.get(eid, ('', ''))[1]}
        except Exception as e:  # noqa: BLE001
            r = {'estilo': eid, 'efeito': var, 'ok': False, 'segundos': round(time.time() - t0, 1), 'erros': [str(e)[:300]]}
        out.append(r)
        print(f"{nome:<28} {'ok ' if r['ok'] else 'ERRO'} {r['segundos']:>6.1f} s  {'; '.join(r['erros'] + r.get('avisos', []))[:90]}", flush=True)
    feitos = [base / (r['estilo'] + (f"-{r['efeito']}" if r['efeito'] else '')) / 'demo.mp4' for r in out if r['ok']]
    folha = base / 'folha-estilos.jpg'
    if feitos:
        entradas = sum((['-ss', '2.5', '-i', str(f)] for f in feitos), [])
        n = len(feitos)
        cols = 6
        rows = (n + cols - 1) // cols
        grafo = ''.join(f'[{k}:v]scale=180:320,setsar=1[v{k}];' for k in range(n))
        grafo += ''.join(f'[v{k}]' for k in range(n)) + f'xstack=inputs={n}:layout=' + '|'.join(
            f'{(k % cols) * 180}_{(k // cols) * 320}' for k in range(n)) + f':fill=white[s]' if n > 1 else '[0:v]scale=180:320[s]'
        rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', *entradas, '-filter_complex', grafo, '-map', '[s]', '-frames:v', '1', '-q:v', '3', str(folha)],
                 tempo_max=300)
    rel = {'onde': 'celular' if hardware.e_android() else 'fora do celular (tempos NÃO valem para o Android)', 'resolucao': f'{W}x{H}',
           'motor': ec.VERSAO_MOTOR, 'demos': out, 'folha': str(folha)}
    (base / 'demos.json').write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\n{sum(r['ok'] for r in out)} de {len(out)} ok. Laudo: {base / 'demos.json'}  ({rel['onde']})")
    return 0 if all(r['ok'] for r in out) else 1


if __name__ == '__main__':
    sys.exit(main())
