from pathlib import Path
import importlib.util,json,os,signal,subprocess,sys,time
repo=Path('/workspace/scratch/ecb4bcf1d97f/estudioclip')
out=repo.parent/'logs'/'VALIDACAO-suite';out.mkdir(exist_ok=True)
(out/'contexto.json').write_text(json.dumps(dict(sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip(),inicio=time.time(),comando='PYTHONPATH=servidor python servidor/testes/teste_*.py, um processo por arquivo'),indent=2))
result=[]
for p in sorted((repo/'servidor/testes').glob('teste_*.py')):
    skip='INTERATIVO_CONTA_REAL' if p.name=='teste_email.py' else ('DEPENDENCIA_YT_DLP' if p.name=='teste_trecho_link.py' and not importlib.util.find_spec('yt_dlp') else '')
    if skip:
        r=dict(teste=p.name,status=skip,exit=None,segundos=0)
    else:
        print('INICIO',p.name,flush=True);t=time.monotonic()
        env=dict(os.environ,PYTHONPATH=str(repo/'servidor'),PYTHONUNBUFFERED='1')
        with (out/(p.stem+'.log')).open('w') as log:
            proc=subprocess.Popen([sys.executable,str(p)],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:rc=proc.wait(timeout=1200);status='PASS' if rc==0 else 'FAIL'
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait();rc=-9;status='TIMEOUT'
        r=dict(teste=p.name,status=status,exit=rc,segundos=round(time.monotonic()-t,2))
    result.append(r);(out/'resultados.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
    print(json.dumps(r,ensure_ascii=False),flush=True)
print('CONCLUIDO',json.dumps({s:sum(r['status']==s for r in result) for s in {r['status'] for r in result}}),flush=True)
