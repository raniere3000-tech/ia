"""Instala as definições das 118 skills (só texto) e gera o relatório de cada uma (etapa K1 do lote 2).

Uso (dentro de servidor/):  python -m skills.relatorio [--sem-baixar] [--catalogo arquivo.json]
- Confere o catálogo do documento contra o manifesto fixado (ids, repositório, caminho, URL).
- Baixa só de raw.githubusercontent.com, no commit fixado, e confere o SHA-256 de cada arquivo.
- Grava ~/.estudioclip/skills/relatorio.json e relatorio.md. Nada é executado; "executores funcionando" é sempre 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banco as db  # noqa: E402
from skills import catalogo as cat  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    arq = Path(args[args.index('--catalogo') + 1]) if '--catalogo' in args else cat.CATALOGO_118
    db.migrar()
    conf = cat.conferir_catalogo(json.loads(arq.read_text(encoding='utf-8')))
    print(f"Catálogo: {conf['total']} itens, {conf['ids_unicos']} ids únicos, {len(conf['com_problema'])} com problema"
          f" -> {'confere com o manifesto' if conf['ok'] else 'NÃO confere'}")
    for x in conf['com_problema'][:20]:
        print('  ', x['id'], '; '.join(x['problemas']))
    cat.sincronizar()
    if '--sem-baixar' not in args:
        def progresso(p, etapa):
            print(f'\r{p:3d}% {etapa[:70]:<70}', end='', flush=True)
        ctx = type('Ctx', (), {'cancelado': staticmethod(lambda: False), 'progresso': staticmethod(progresso)})()
        r = cat.instalar(None, ctx)
        print(f"\nInstaladas agora {len(r['instaladas'])}, já estavam {len(r['ja_estavam'])}, falhas {len(r['falhas'])}")
        for f in r['falhas'][:30]:
            print('  falha:', f['id'], f['motivo'])
    rel = cat.relatorio()
    print(f"\nRelatório: {rel['total']} skills | definições instaladas {rel['definicoes_instaladas']} | "
          f"usáveis pelos agentes {rel['usaveis_pelos_agentes']} | executores funcionando {rel['executores_funcionando']}")
    print('Por estado:', ', '.join(f'{k} {v}' for k, v in sorted(rel['por_estado'].items())))
    print('Arquivos:', Path(rel['pasta']) / 'relatorio.json', 'e relatorio.md')
    return 0 if conf['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
