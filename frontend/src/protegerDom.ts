// Tradutores do navegador (Google Tradutor) e algumas extensões trocam os textos da página por <font>.
// Isso faz o React falhar com "insertBefore/removeChild: o nó não é filho deste nó" e a tela some.
// Aqui deixamos essas duas operações tolerantes: se o nó já foi movido por fora, seguimos sem quebrar.
if(typeof Node==='function'&&Node.prototype){
  const remover=Node.prototype.removeChild;
  Node.prototype.removeChild=function<T extends Node>(this:Node,filho:T):T{
    if(filho.parentNode!==this){ if(filho.parentNode) filho.parentNode.removeChild(filho); return filho; }
    return remover.call(this,filho) as T;
  };
  const inserir=Node.prototype.insertBefore;
  Node.prototype.insertBefore=function<T extends Node>(this:Node,novo:T,ref:Node|null):T{
    if(ref&&ref.parentNode!==this) return inserir.call(this,novo,null) as T;
    return inserir.call(this,novo,ref) as T;
  };
}
export {};
