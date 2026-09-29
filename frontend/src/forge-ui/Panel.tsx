import {useEffect,useRef,useState, type ReactNode} from 'react';
import {clampPanel,defaults} from './state.mjs';
export function Panel({children,tab,onTab,hidden,onClose}:{children:ReactNode;tab:string;onTab:(s:string)=>void;hidden:boolean;onClose:()=>void}) {
  const [box,setBox]=useState<typeof defaults>(()=>{try{return clampPanel(JSON.parse(localStorage.getItem('forge.panel')||'{}'),innerWidth,innerHeight)}catch{return defaults}});
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{localStorage.setItem('forge.panel',JSON.stringify({...box,tab,closed:hidden}))},[box,tab,hidden]);
  useEffect(()=>{const resize=()=>setBox(b=>clampPanel(b,innerWidth,innerHeight));window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize)},[]);
  function drag(event:React.PointerEvent,resize=false){
    if ((event.target as HTMLElement).closest('button')) return;
    const start={...box};
    const element=event.currentTarget as HTMLElement;
    element.setPointerCapture(event.pointerId);
    element.onpointermove=e=>setBox(clampPanel(resize?{...box,width:start.width+e.clientX-event.clientX,height:start.height+e.clientY-event.clientY}:{...box,x:start.x+e.clientX-event.clientX,y:start.y+e.clientY-event.clientY},innerWidth,innerHeight));
    element.onpointerup=()=>{element.onpointermove=null;element.onpointerup=null};
  }
  return <section ref={ref} className="forge-panel" aria-label="Painel FORGE" style={{display:hidden?'none':undefined,left:box.x,top:box.y,width:box.width,height:box.minimized?52:box.height}}>
    <header className="panel-handle" onPointerDown={e=>drag(e)}><span className="mini-brand">F<span> / </span>FORGE</span><span className="window-actions"><button title={box.minimized?'Expandir':'Minimizar'} onClick={()=>setBox({...box,minimized:!box.minimized})}>{box.minimized?'+':'−'}</button><button title="Fechar FORGE" onClick={onClose}>×</button></span></header>
    {!box.minimized&&<><nav className="tabs">{['Criar','Modelo','Efeitos','Projeto'].map(t=><button key={t} onClick={()=>onTab(t)} aria-selected={tab===t} className={tab===t?'active':''}>{t}</button>)}</nav><div className="panel-content">{children}</div><footer className="panel-footer"><span>● PROCESSAMENTO LOCAL</span><button title="Abrir diagnóstico" onClick={()=>onTab('Diagnóstico')}>Diagnóstico ↗</button></footer><div className="resize-handle" onPointerDown={e=>drag(e,true)} aria-label="Redimensionar painel"/></>}
  </section>
}
