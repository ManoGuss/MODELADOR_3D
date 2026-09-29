export async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response = await fetch(`/api${path}`, {method, headers:body ? {'Content-Type':'application/json'} : {}, body:body ? JSON.stringify(body) : undefined, signal:AbortSignal.timeout(15000)});
  if (!response.ok) {
    const data = await response.json().catch(()=>({}));
    throw new Error(typeof data.detail==='string' ? data.detail : `Não foi possível concluir a operação (${response.status}).`);
  }
  return response.json();
}
