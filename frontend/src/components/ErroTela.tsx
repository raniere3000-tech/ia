import { Component, type ReactNode } from 'react';

/** Se uma aba quebrar, mostra o erro em vez de deixar a tela preta. */
export default class ErroTela extends Component<{children:ReactNode;chave:string},{erro:Error|null}>{
  state={erro:null as Error|null};
  static getDerivedStateFromError(erro:Error){ return {erro}; }
  componentDidCatch(erro:Error,info:unknown){ console.error('Erro na aba',erro,info); }
  componentDidUpdate(p:{chave:string}){ if(p.chave!==this.props.chave&&this.state.erro) this.setState({erro:null}); }
  render(){
    if(!this.state.erro) return this.props.children;
    return <section className="panel empty-state">
     <h2>Algo deu errado nesta tela</h2>
     <p className="hint">Seu trabalho continua salvo neste navegador. Toque em Tentar de novo. Se repetir, mande um print desta mensagem:</p>
     <pre className="erro-tela">{String(this.state.erro?.message||this.state.erro)}</pre>
     <button className="primary" onClick={()=>this.setState({erro:null})}>Tentar de novo</button>
    </section>;
  }
}
