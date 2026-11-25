"""F2.02: compara frames renderizados, plano e recibos, com mídia própria registrada."""
import array,json,math,os,sys,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
TMP=Path(tempfile.mkdtemp(prefix='ec-efeitos-reais-'))
os.environ.update(DADOS=str(TMP),BANCO_ARQ=str(TMP/'studio.sqlite'),ESTEIRA_COMPLETA='0')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import banco as db
import contratos as ct
import editor_ia as ed
import projetos as pj
import renderizador as rd
import agente as ag

db.migrar()
BASE=TMP/'base.mp4'
subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=30:d=3',
                '-f','lavfi','-i','sine=f=440:d=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(BASE)],check=True)

def frame(p,t):
    return subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])

def dif(a,b):
    return sum(abs(x-y) for x,y in zip(a,b))/max(1,min(len(a),len(b)))


def intensidade(arq, inicio, frequencia):
    pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(inicio), '-i', str(arq),
                                   '-map', '0:a:0', '-t', '0.2', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    amostras = array.array('f', pcm)
    if sys.byteorder != 'little':
        amostras.byteswap()
    theta = math.tau * frequencia / 48000
    return abs(sum(x * complex(math.cos(theta * i), math.sin(theta * i)) for i, x in enumerate(amostras))) / len(amostras)


class EfeitosReais(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'A5_EFEITOS_REAIS':'1'});self.env.start();self.addCleanup(self.env.stop)
    def plano(self,efeitos):
        return ct.validar_plano({'clips':[{'source':'principal','in_ms':0,'out_ms':3000}], 'effects':efeitos,'target_aspect_ratio':'16:9'})
    def render(self,nome,efeitos,ass=None):
        p=TMP/(nome+'.mp4');ed._finalizar_efeitos(self.plano(efeitos),BASE,p,ass=ass);return p

    def test_zoom_so_no_intervalo_comprovado_por_frames(self):
        controle=self.render('controle',[])
        saida=self.render('zoom',[{'tipo':'zoom','nivel':1.4,'ini_ms':1000,'fim_ms':2000}])
        antes=dif(frame(controle,.3),frame(saida,.3));durante=dif(frame(controle,1.5),frame(saida,1.5));depois=dif(frame(controle,2.6),frame(saida,2.6))
        print(f'Zoom: diferença média RGB antes={antes:.2f}, durante={durante:.2f}, depois={depois:.2f}')
        self.assertGreater(durante,10)
        # H.264 usa predição entre quadros; fora do efeito a diferença deve ser
        # pequena em relação à mudança visual medida no intervalo aplicado.
        self.assertLess(max(antes,depois),durante*.2)
        r=json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual((r['planejados'],r['aplicados'],r['falhas']),(1,1,0))
        self.assertEqual(r['arquivo_sha'],rd.sha256(saida))

    def test_broll_registrado_e_licenca_obrigatoria(self):
        foto=TMP/'blue.png'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=160x90','-frames:v','1',str(foto)],check=True)
        aid=pj.registrar_asset(foto,'blue.png','image/png')['asset']['id']
        e={'tipo':'broll','asset':aid,'direitos':'meu','ini_ms':1000,'fim_ms':2000}
        saida=self.render('broll',[e]);q=frame(saida,1.5)
        self.assertGreater(sum(q[2::3])/len(q[2::3]),200)
        self.assertLess(sum(q[0::3])/len(q[0::3]),35)
        with self.assertRaises(ct.ErroContrato):self.plano([dict(e,direitos='desconhecido')])
        with patch.dict(os.environ,{'A5_EFEITOS_REAIS':'0'}),self.assertRaises(ct.ErroContrato):self.plano([e])

    def test_legenda_real_e_noop_nao_conta_como_efeito(self):
        ass=TMP/'caption.ass';t=dict(ag.PADRAO['cortes']['template'],gancho=False,legenda='destaque')
        ass.write_text(ag.montar_ass([(0.5,1.8,'PALAVRA')],0,3,t,'',160,90))
        cap={'tipo':'caption','ligado':1,'tamanho':.07,'altura':.5}
        saida=self.render('legenda',[cap],ass)
        self.assertGreater(dif(frame(BASE,1),frame(saida,1)),1)
        noop=self.render('noop',[{'tipo':'zoom','nivel':1,'ini_ms':0,'fim_ms':3000}])
        self.assertEqual(json.loads(noop.with_suffix('.efeitos.json').read_text())['aplicados'],0)

    def test_falha_nao_substitui_video_anterior(self):
        saida=TMP/'anterior.mp4';saida.write_bytes(b'VERSAO ANTERIOR')
        p=self.plano([{'tipo':'broll','asset':'a'*16,'direitos':'meu','ini_ms':0,'fim_ms':1000}])
        with self.assertRaises(pj.ErroProjeto):ed._finalizar_efeitos(p,BASE,saida)
        self.assertEqual(saida.read_bytes(),b'VERSAO ANTERIOR')
        self.assertEqual(json.loads(saida.with_suffix('.efeitos.json').read_text())['status'],'falhou')

    def test_editor_nao_declara_efeitos_sem_recibo_do_render(self):
        import pipeline as pl
        r=pl.criar('manual','sem-recibo','Teste')
        with self.assertRaises(FileNotFoundError):
            ed.rodar(r['id'],'sem-recibo',self.plano([]),lambda p:BASE,lambda p:{})

    def test_executor_do_corte_aplica_fade_e_emite_recibo(self):
        t=dict(ag.PADRAO['cortes']['template'],resolucao=360,gancho=False,legenda='nenhuma')
        plano=self.plano([{'tipo':'fade','entrada_ms':300,'saida_ms':300},{'tipo':'zoom','nivel':1.2,'ini_ms':1000,'fim_ms':2000}])
        saida=TMP/'corte.mp4'
        ed.executar_corte(plano,BASE,{'ini':0,'fim':3,'gancho':''},[],t,saida,TMP)
        self.assertAlmostEqual(rd.duracao(saida),3,delta=.25)
        recibo=json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['aplicados'],2)
        q0=frame(saida,.03);q1=frame(saida,.6)
        self.assertLess(sum(q0)/len(q0),sum(q1)/len(q1)*.6)

    def test_montagem_com_velocidade_por_trecho_e_audio_sincronizado(self):
        saida = TMP / 'velocidade.mp4'
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE, clips=[
            {'in_ms': 0, 'out_ms': 1000},
            {'in_ms': 1500, 'out_ms': 2100, 'speed': 0.5},
            {'in_ms': 2400, 'out_ms': 3000, 'speed': 2},
        ], protected_hook={'in_ms': 0, 'out_ms': 900})
        plano = ct.validar_plano(plano)
        with patch.dict(ct.ASPECTOS, {'16:9': (160, 90)}):
            ed.executar_importado(plano, BASE, saida)
        streams = {s['codec_type']: float(s['duration']) for s in rd.sonda(saida)['streams']}
        self.assertAlmostEqual(streams['video'], 2.5, delta=0.12)
        self.assertAlmostEqual(streams['audio'], streams['video'], delta=0.10)
        self.assertGreater(dif(frame(BASE, 1.25), frame(saida, 1.25)), 10)
        palavra = ed.palavras_saida(plano, [(1.6, 1.7, 'palavra')])[0]
        self.assertAlmostEqual(palavra[0], 1.2)
        self.assertAlmostEqual(palavra[1], 1.4)
        recibo = json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['arquivo_sha'], rd.sha256(saida))
        self.assertEqual(recibo['montagem']['trechos'], plano['clips'])
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(saida), '-f', 'null', '-'], check=True)

    def test_montagem_sem_audio_preserva_gancho_de_abertura(self):
        fonte = TMP / 'silencioso.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(BASE), '-an', '-c:v', 'copy', str(fonte)], check=True)
        tpl = dict(ag.PADRAO['cortes']['template'], resolucao=360, gancho=True, legenda='nenhuma', formato='16:9')
        corte = {'ini': 0, 'fim': 3, 'gancho': 'GANCHO INTEIRO'}
        with patch.dict(os.environ, {'A5_EDITOR_PRO': '1'}):
            plano = ed.plano_do_corte(corte, tpl, 3)
        self.assertEqual(plano['protected_hook'], {'in_ms': 0, 'out_ms': 3000})
        _, mudancas = ed.corrigir(plano, [{'acao': 'ajustar_inicio', 'delta_ms': 400}])
        self.assertEqual(mudancas, [])
        plano['effects'].append({'tipo': 'fade', 'saida_ms': 200})
        saida = TMP / 'silencioso-editado.mp4'
        ed.executar_corte(plano, fonte, corte, [], tpl, saida, TMP)
        self.assertFalse(ed.tem_audio(saida))
        self.assertAlmostEqual(rd.duracao(saida), 3, delta=0.12)
        self.assertEqual(json.loads(saida.with_suffix('.efeitos.json').read_text())['montagem']['gancho_protegido'],
                         plano['protected_hook'])

    def test_regiao_na_borda_e_fallback_quando_nao_cabe_no_recorte(self):
        fonte = TMP / 'roi-fonte.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=240x100:r=30:d=2',
                        '-vf', 'drawbox=x=205:y=0:w=35:h=100:color=white:t=fill', '-c:v', 'libx264', str(fonte)], check=True)
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE, clips=[{'in_ms': 0, 'out_ms': 2000}],
                     target_aspect_ratio='1:1')
        roi = {'tipo': 'reframe', 'modo': 'roi', 'x': 0.86, 'y': 0.1, 'w': 0.13, 'h': 0.8}
        destino = TMP / 'roi.mp4'
        encaixado = TMP / 'roi-encaixado.mp4'
        with patch.dict(ct.ASPECTOS, {'1:1': (100, 100)}):
            ed.executar_importado(dict(plano, effects=[roi]), fonte, destino)
            ed.executar_importado(dict(plano, effects=[dict(roi, x=0.1, w=0.89)]), fonte, encaixado)
        frame_roi = frame(destino, 0.8)
        frame_fallback = frame(encaixado, 0.8)
        self.assertTrue(all(p > 235 for p in frame_roi[(50 * 100 + 91) * 3: (50 * 100 + 91) * 3 + 3]))
        self.assertLess(max(frame_fallback[:300]), 10)  # faixa completa de encaixe
        self.assertTrue(all(p > 235 for p in frame_fallback[(50 * 100 + 96) * 3: (50 * 100 + 96) * 3 + 3]))
        recibo = json.loads(encaixado.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['efeitos'][0]['status'], 'fallback')
        self.assertEqual(recibo['aplicados'], 0)

    def test_cor_e_entrega_tem_efeito_no_mp4(self):
        destino = TMP / 'cor-entrega.mp4'
        controle = TMP / 'cor-controle.mp4'
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE,
                     delivery={'fps': 25, 'crf': 25, 'limite_kbps': 650})
        e = {'tipo': 'cor', 'exposicao_ev': 0.6, 'temperatura_k': 4500, 'saturacao': 0.7, 'contraste': 1.1}
        with patch.dict(ct.ASPECTOS, {'16:9': (160, 90)}):
            ed.executar_importado(plano, BASE, controle)
            ed.executar_importado(dict(plano, effects=[e]), BASE, destino)
        antes, depois = frame(controle, 1.2), frame(destino, 1.2)
        self.assertGreater(dif(antes, depois), 8)
        self.assertGreater(sum(depois) / len(depois), sum(antes) / len(antes))
        recibo = json.loads(destino.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['efeitos'][0]['status'], 'aplicado')
        self.assertEqual(recibo['exportacao']['codec'], 'h264')
        self.assertEqual(recibo['exportacao']['fps'], '25/1')
        self.assertEqual(recibo['exportacao']['configuracao'], plano['delivery'])
        self.assertLess(int(recibo['exportacao']['bitrate_bps']), 650_000)
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(destino), '-f', 'null', '-'], check=True)

    def test_cor_sem_filtro_disponivel_registra_fallback(self):
        saida = TMP / 'cor-fallback.mp4'
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE, effects=[{'tipo': 'cor', 'exposicao_ev': 0.5}])
        with patch('visual_presets.filtros_disponiveis', return_value=frozenset()):
            ed._finalizar_efeitos(plano, BASE, saida)
        recibo = json.loads(saida.with_suffix('.efeitos.json').read_text())
        self.assertEqual(recibo['efeitos'][0]['status'], 'fallback')
        self.assertIn('exposure', recibo['efeitos'][0]['motivo'])
        self.assertEqual(recibo['aplicados'], 0)

    def test_tratamento_audio_e_camada_com_ducking_no_tempo_certo(self):
        fala = TMP / 'fala.mp4'
        musica = TMP / 'trilha.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(BASE), '-f', 'lavfi', '-i',
                        r'aevalsrc=0.65*sin(2*PI*440*t)*lt(t\,1.45):d=3', '-map', '0:v:0', '-map', '1:a:0',
                        '-c:v', 'copy', '-c:a', 'aac', str(fala)], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=760:d=2.5', str(musica)], check=True)
        aid = pj.registrar_asset(musica, 'trilha.wav', 'audio/wav')['asset']['id']
        camada = {'tipo': 'som', 'asset': aid, 'direitos': 'meu', 'categoria': 'trilha',
                  'ini_ms': 500, 'fim_ms': 2800, 'ganho_db': -6}
        p = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE)
        bruto = TMP / 'mix-controle.mp4'
        ducking = TMP / 'mix-duck.mp4'
        tratado = TMP / 'audio-tratado.mp4'
        ed._finalizar_efeitos(dict(p, effects=[camada]), fala, bruto)
        ed._finalizar_efeitos(dict(p, effects=[dict(camada, ducking='ligado')]), fala, ducking)
        ed._finalizar_efeitos(dict(p, effects=[{'tipo': 'audio', 'eq_hz': 440, 'eq_db': -6,
                                              'compressao': 3, 'limiar_db': -24, 'reducao_ruido_db': 12}]), fala, tratado)
        self.assertLess(intensidade(bruto, 0.1, 760), intensidade(bruto, 0.9, 760) * 0.10)
        self.assertLess(intensidade(ducking, 0.9, 760), intensidade(bruto, 0.9, 760) * 0.70)
        self.assertGreater(intensidade(ducking, 2.15, 760), intensidade(bruto, 2.15, 760) * 0.9)
        self.assertLess(intensidade(tratado, 0.9, 440), intensidade(fala, 0.9, 440) * 0.6)
        recibo = json.loads(ducking.with_suffix('.efeitos.json').read_text())
        self.assertTrue(recibo['efeitos'][0]['ducking'])
        self.assertEqual(recibo['efeitos'][0]['asset_sha'], rd.sha256(musica))
        self.assertEqual(recibo['arquivo_sha'], rd.sha256(ducking))
        with self.assertRaises(ct.ErroContrato):
            ct.validar_plano(dict(p, effects=[dict(camada, direitos='desconhecido')]))

    def test_composicao_chroma_e_mascara_comprovadas_por_pixels(self):
        cena = TMP / 'chroma.png'
        mascara = TMP / 'mascara.png'
        for destino, fundo, frente in [(cena, 'lime', 'red'), (mascara, 'black', 'white')]:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color={fundo}:s=160x90',
                            '-vf', f'drawbox=w=80:h=90:color={frente}:t=fill', '-frames:v', '1', str(destino)], check=True)
        ids = [pj.registrar_asset(p, p.name, 'image/png')['asset']['id'] for p in (cena, mascara)]
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE)
        camada = {'tipo': 'camada', 'asset': ids[0], 'direitos': 'meu', 'x': 0, 'y': 0, 'w': 1, 'h': 1,
                  'ini_ms': 800, 'fim_ms': 2000}
        controle, chroma, alpha = (TMP / f'{nome}-composicao.mp4' for nome in ('controle', 'chroma', 'alpha'))
        ed._finalizar_efeitos(plano, BASE, controle)
        ed._finalizar_efeitos(dict(plano, effects=[dict(camada, chroma='verde')]), BASE, chroma)
        ed._finalizar_efeitos(dict(plano, effects=[dict(camada, mascara_asset=ids[1])]), BASE, alpha)
        def pixel(raw, x, y=30):
            i = (y * 160 + x) * 3
            return raw[i:i+3]
        normal, c, a = (frame(p, 1.2) for p in (controle, chroma, alpha))
        for q in (c, a):
            r, g, b = pixel(q, 25)
            self.assertGreater(r, 220)
            self.assertLess(max(g, b), 25)
            self.assertLess(dif(pixel(q, 130), pixel(normal, 130)), 12)
        self.assertLess(dif(frame(controle, 0.3), frame(chroma, 0.3)), 10)
        dados = json.loads(alpha.with_suffix('.efeitos.json').read_text())
        self.assertEqual(dados['efeitos'][0]['mascara_sha'], rd.sha256(mascara))
        self.assertEqual(dados['arquivo_sha'], rd.sha256(alpha))

    def test_mascara_retangular_e_desfoque_temporal(self):
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE)
        escuro={'tipo': 'mascara', 'x': 0, 'y': 0, 'w': 0.4, 'h': 0.4, 'ini_ms': 700, 'fim_ms': 1900}
        blur={'tipo': 'desfoque_movimento', 'quadros': 5, 'ini_ms': 700, 'fim_ms': 1900}
        mascara, temporal, controle = (TMP / f'{nome}-mascara.mp4' for nome in ('geo', 'temporal', 'controle'))
        ed._finalizar_efeitos(dict(plano, effects=[escuro]), BASE, mascara)
        ed._finalizar_efeitos(dict(plano, effects=[blur]), BASE, temporal)
        ed._finalizar_efeitos(plano, BASE, controle)
        self.assertLess(max(frame(mascara, 1.3)[:120]), 12)
        self.assertGreater(max(frame(mascara, 0.3)[:120]), 60)
        self.assertGreater(dif(frame(temporal, 1.3), frame(controle, 1.3)), 3)

    def test_keyframes_e_easing_movem_camada_na_saida(self):
        cinza = TMP / 'cinza-motion.mp4'
        figura = TMP / 'quadrado.png'
        for fonte, destino, opcoes in [('gray:s=160x90:d=3', cinza, ['-c:v', 'libx264']),
                                        ('red:s=32x20', figura, ['-frames:v', '1'])]:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color={fonte}', *opcoes, str(destino)], check=True)
        aid = pj.registrar_asset(figura, figura.name, 'image/png')['asset']['id']
        inicio = {'ms': 0, 'x': 0.1, 'y': 0.2}
        fim = {'ms': 1600, 'x': 0.7, 'y': 0.2}
        camada = {'tipo': 'camada', 'asset': aid, 'direitos': 'meu', 'x': 0.1, 'y': 0.2, 'w': 0.2, 'h': 0.3,
                  'ini_ms': 500, 'fim_ms': 2300}
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE)
        linear, suave = (TMP / f'{x}-movimento.mp4' for x in ('linear', 'suave'))
        ed._finalizar_efeitos(dict(plano, effects=[dict(camada, keyframes=[inicio, fim])]), cinza, linear)
        ed._finalizar_efeitos(dict(plano, effects=[dict(camada, keyframes=[inicio, dict(fim, easing='suave')])]), cinza, suave)

        def coluna(arq, t):
            pixels = frame(arq, t)
            return next(i for i in range(160) if pixels[(30 * 160 + i) * 3] > 220)

        self.assertGreater(coluna(linear, 0.9), coluna(suave, 0.9) + 6)
        self.assertGreater(coluna(suave, 1.9), coluna(suave, 0.9) + 45)
        self.assertEqual(json.loads(suave.with_suffix('.efeitos.json').read_text())['aplicados'], 1)
        with self.assertRaises(ct.ErroContrato):
            ct.validar_plano(dict(plano, effects=[dict(camada, keyframes=[inicio, dict(fim, x=0.99)])]))

    def test_legenda_pulsa_apenas_na_palavra_com_enfase(self):
        cinza = TMP / 'cinza-legenda.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=gray:s=320x180:d=3',
                        '-c:v', 'libx264', str(cinza)], check=True)
        tpl = dict(ag.PADRAO['cortes']['template'], gancho=False, legenda='destaque')
        cap = {'tipo': 'caption', 'ligado': 1, 'altura': 0.5, 'animacao': 'pulso', 'enfase': ['lua']}
        plano = dict(self.plano([]), schema_version=ct.SCHEMA_TIMELINE, effects=[cap])
        ass = TMP / 'pulso.ass'
        t = ed.tpl_do_plano(tpl, ct.validar_plano(plano))
        ass.write_text(ag.montar_ass([(0.6, 1.1, 'MAR'), (1.2, 1.7, 'LUA!')], 0, 3, t, '', 320, 180))
        destino = TMP / 'pulso.mp4'
        ed._finalizar_efeitos(plano, cinza, destino, ass=ass)

        def amarelos(t):
            pixels = frame(destino, t)
            return sum(r > 160 and g > 130 and b < 130 for r, g, b in zip(pixels[0::3], pixels[1::3], pixels[2::3]))

        self.assertLess(amarelos(0.85), 5)
        self.assertGreater(amarelos(1.4), 15)
        self.assertIn(r'\t(0,90', ass.read_text())

if __name__=='__main__':unittest.main()
