export const defaults = {x:28,y:100,width:368,height:560,closed:false,minimized:false,tab:'Criar'};
export function clampPanel(value, width, height) {
  const safe = {...defaults,...value};
  for (const key of ['x','y','width','height']) if (!Number.isFinite(safe[key])) safe[key]=defaults[key];
  safe.width=Math.max(280,Math.min(safe.width,width-24));
  safe.height=Math.max(240,Math.min(safe.height,height-100));
  safe.x=Math.max(12,Math.min(safe.x,width-safe.width-12));
  safe.y=Math.max(76,Math.min(safe.y,height-(safe.minimized?48:safe.height)-24));
  if (!['Criar','Modelo','Efeitos','Projeto','Diagnóstico'].includes(safe.tab)) safe.tab='Criar';
  safe.closed=safe.closed===true; safe.minimized=safe.minimized===true;
  return safe;
}
