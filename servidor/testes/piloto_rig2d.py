"""Piloto da etapa T2: 30 s, dois personagens, três cenas com três planos cada (WS, MS, CU), diálogo,
caminhada, gestos, poses, IK (alcançar) e objeto na mão. Mede o tempo e confere o vídeo final.

Uso:  python testes/piloto_rig2d.py [pasta_saida] [--leve]
      --leve = 540x960 (para medir rápido no celular)

A voz é SINTÉTICA de teste (sílabas no tom de cada personagem, uma por sílaba do texto), porque aqui não há TTS.
No servidor de verdade a voz vem do Gemini ou da gravação; a boca segue o mesmo caminho (texto + volume).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))
import estilos_codigo as ec  # noqa: E402
import renderizador as rd  # noqa: E402
import rig2d  # noqa: E402

PERSONAGENS = {'ana': rig2d.validar_personagem({'nome': 'Ana', 'cabelo_tipo': 'longo', 'roupa': '#e63946', 'calca': '#264653'}),
               'beto': rig2d.validar_personagem({'nome': 'Beto', 'cabelo_tipo': 'cacheado', 'corpo': 'forte', 'roupa': '#3a86ff', 'acessorio': 'bone'})}
TOM = {'ana': 230, 'beto': 135}

CENAS = [
    {'personagem': 'ana', 'texto': 'Beto! Achei uma caixa misteriosa perto do lago. Você sabe de quem é?',
     'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'expressao': 'surpreso',
                 'acoes': [{'t': 0.2, 'tipo': 'andar', 'alvo': 'centro', 'dur': 2.4}, {'t': 3.0, 'tipo': 'acenar'}, {'t': 5.6, 'tipo': 'apontar', 'alvo': 'direita'}]},
                {'personagem_id': 'beto', 'posicao': 'direita', 'expressao': 'neutro',
                 'acoes': [{'t': 0.5, 'tipo': 'olhar', 'alvo': 'esquerda', 'dur': 3.0}, {'t': 4.0, 'tipo': 'pose', 'pose': 'bracos_cruzados', 'dur': 5.0}]}],
     'planos': [{'plano': 'WS'}, {'plano': 'MS', 'personagem': 'ana'}, {'plano': 'CU', 'personagem': 'beto'}]},
    {'personagem': 'beto', 'texto': 'Deixa eu ver. Ela é leve, mas tem alguma coisa rolando dentro dela.',
     'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'expressao': 'preocupado',
                 'acoes': [{'t': 0.4, 'tipo': 'pose', 'pose': 'pensativo', 'dur': 3.5}, {'t': 6.5, 'tipo': 'reagir'}]},
                {'personagem_id': 'beto', 'posicao': 'direita', 'expressao': 'neutro',
                 'acoes': [{'t': 0.3, 'tipo': 'alcancar', 'alvo': 'chao', 'lado': 'esquerda', 'objeto': 'caixa', 'dur': 1.6},
                           {'t': 2.2, 'tipo': 'segurar', 'objeto': 'caixa', 'dur': 4.0}, {'t': 6.6, 'tipo': 'entregar', 'alvo': 'esquerda', 'objeto': 'caixa', 'dur': 2.4}]}],
     'planos': [{'plano': 'WS'}, {'plano': 'MS', 'personagem': 'beto'}, {'plano': 'CU', 'personagem': 'ana'}]},
    {'personagem': 'ana', 'texto': 'É uma bola! Era do meu irmão. Obrigada, Beto, você é demais!',
     'elenco': [{'personagem_id': 'ana', 'posicao': 'esquerda', 'expressao': 'feliz',
                 'acoes': [{'t': 0.3, 'tipo': 'segurar', 'objeto': 'bola', 'dur': 3.4}, {'t': 4.2, 'tipo': 'pose', 'pose': 'comemorar', 'dur': 2.2},
                           {'t': 7.0, 'tipo': 'rir'}]},
                {'personagem_id': 'beto', 'posicao': 'direita', 'expressao': 'feliz',
                 'acoes': [{'t': 1.0, 'tipo': 'pose', 'pose': 'maos_na_cintura', 'dur': 4.5}, {'t': 6.0, 'tipo': 'acenar'}]}],
     'planos': [{'plano': 'MS', 'personagem': 'ana'}, {'plano': 'CU', 'personagem': 'ana'}, {'plano': 'WS'}]},
]


def voz_teste(texto: str, tom: int, dur: float, arq: Path):
    """Uma sílaba por vogal do texto (volume e timbre variando), com pausas nas vírgulas e pontos. Só para teste."""
    sil = max(1, len(rig2d.nucleos(texto)))
    fala = min(dur - 0.8, sil * 0.2)
    taxa = sil / fala
    expr = (f"0.55*sin(2*PI*({tom}+{tom * 0.25:.0f}*sin(2*PI*0.9*t))*t)*(0.6+0.4*sin(2*PI*{tom * 2}*t))"
            f"*max(0,sin(PI*{taxa:.3f}*(t-0.4)))*between(t,0.4,{0.4 + fala:.2f})")
    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f"aevalsrc='{expr}':s=24000:d={dur}", '-ac', '1',
              '-c:a', 'pcm_s16le', str(arq)], tempo_max=60)


def main():
    leve = '--leve' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    saida_dir = Path(args[0]) if args else Path.home() / 'estudioclip-piloto-t2'
    saida_dir.mkdir(parents=True, exist_ok=True)
    W, H = (540, 960) if leve else ec.FORMATOS['9:16']
    dur = 10.0
    clipes, relatorio = [], {'resolucao': f'{W}x{H}', 'cenas': [], 'voz': 'sintética de teste (sem TTS neste aparelho)'}
    t_tot = time.time()
    for i, base in enumerate(CENAS):
        pasta = saida_dir / f'cena{i + 1}'
        pasta.mkdir(exist_ok=True)
        c = ec.validar_cena(dict(base, cenario_id='parque'))
        c['_personagens'] = PERSONAGENS
        c['_cenario'] = {'tipo': 'parque', 'horario': 'tarde' if i == 2 else 'dia'}
        wav = pasta / 'voz.wav'
        voz_teste(c['texto'], TOM[base['personagem']], dur, wav)
        c['_audio'] = str(wav)
        arq = pasta / 'cena.mp4'
        t0 = time.time()
        rd.rodar(ec.montar('animado2d', c, W, H, dur, pasta, None, wav, arq), tempo_max=1800)
        seg = time.time() - t0
        _nv, modo = rig2d.visemas(wav, dur, c['texto'])
        relatorio['cenas'].append({'cena': i + 1, 'segundos': round(seg, 1), 'seg_por_seg': round(seg / dur, 2), 'boca': modo,
                                   'acoes': sorted({a['tipo'] for e in c['elenco'] for a in e['acoes']}),
                                   'planos': [p['plano'] for p in c['planos']]})
        print(f'cena {i + 1}: {seg:.1f} s ({seg / dur:.2f} s por segundo de vídeo), boca: {modo}', flush=True)
        clipes.append(arq)
    final = saida_dir / 'piloto-t2.mp4'
    rd.concatenar(clipes, final, saida_dir)
    conf = rd.conferir(final, saida_dir, {'largura': W, 'altura': H, 'duracao': dur * len(CENAS)})
    # folha de contato: começo, meio e fim de cada plano (para conferir rosto, roupa e proporção nos planos)
    tempos = []
    for k in range(len(CENAS)):
        for (a, b) in ec.tempos_planos([{'plano': 'x', 'peso': 1.0}] * 3, dur):
            tempos.append(k * dur + (a + b) / 2)
    folha = saida_dir / 'folha-contato.jpg'
    sel = '+'.join(f'between(t,{t:.2f},{t + 0.04:.2f})' for t in tempos)
    rd.rodar(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(final), '-vf', f"select='{sel}',scale=270:-2,tile=9x1:padding=4:color=white",
              '-frames:v', '1', '-q:v', '3', str(folha)], tempo_max=300)
    bib = {k: rig2d.biblioteca(p, Path.home() / '.estudioclip' / 'rig2d')['assinatura'] for k, p in PERSONAGENS.items()}
    relatorio.update(total_segundos=round(time.time() - t_tot, 1), conferencia={'ok': conf['ok'], 'erros': conf['erros'], 'avisos': conf['avisos']},
                     duracao=conf['duracao'], assinaturas=bib, arquivo=str(final), folha=str(folha))
    (saida_dir / 'relatorio.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))
    return 0 if conf['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
