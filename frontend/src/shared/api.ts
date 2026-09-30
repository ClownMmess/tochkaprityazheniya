let token:string|null=null;
export function setToken(value:string|null){token=value;}
export class ApiError extends Error{constructor(public status:number,message:string){super(message);}}
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
 const headers=new Headers(options.headers);if(options.body)headers.set('Content-Type','application/json');
 if(token)headers.set('Authorization',`Bearer ${token}`);
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),path.startsWith('/search/')?60000:20000);
 try{
  const r=await fetch(`/api/v1${path}`,{...options,headers,signal:controller.signal});
  if(r.status===204)return undefined as T;
  const data=await r.json();
  if(!r.ok){if(r.status===401){token=null;window.dispatchEvent(new Event('session-expired'));}
   throw new ApiError(r.status,data?.error?.message||'Не удалось выполнить запрос');}
  return data as T;
 }catch(e){if(e instanceof DOMException && e.name==='AbortError')throw new Error('Сервер не ответил вовремя. Повторите запрос.');throw e;}
 finally{clearTimeout(timer);}
}
export const body=(data:unknown)=>JSON.stringify(data);
export function safeUrl(value:string|null|undefined):string|undefined{
 try{const u=new URL(value||'');return u.protocol==='https:'||u.protocol==='http:'?u.href:undefined;}catch{return undefined;}
}
