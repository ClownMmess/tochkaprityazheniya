type Bridge={initData:string;initDataUnsafe?:{start_param?:string};shareMaxContent?:(params:{text:string;link:string})=>Promise<unknown>};
declare global{interface Window{WebApp?:Bridge}}
export function rawInitData(){return window.WebApp?.initData||new URLSearchParams(window.location.hash.slice(1)).get('WebAppData')||'';}
export function choiceToken(search=window.location.search,start=window.WebApp?.initDataUnsafe?.start_param):string|null{
 // start_param is navigation only. It never identifies or authorizes the user.
 const fragment=new URLSearchParams(window.location.hash.slice(1));
 const signedStart=new URLSearchParams(fragment.get('WebAppData')||'').get('start_param');
 const value=new URLSearchParams(search).get('choice') || (start||signedStart||'').replace(/^choice_/, '');
 return value && /^[a-zA-Z0-9_-]{1,128}$/.test(value)?value:null;
}
export function choiceLink(botName:string,token:string){
 if(!/^[a-zA-Z0-9_]+$/.test(botName)||!/^[a-zA-Z0-9_-]{1,128}$/.test(token))throw Error('Неверные параметры ссылки');
 return `https://max.ru/${botName}?startapp=choice_${token}`;
}
export async function shareChoice(title:string,link:string):Promise<string>{
 const u=new URL(link);if(!['https:','http:'].includes(u.protocol))throw Error('Неверная ссылка');
 if(u.hostname==='max.ru' && rawInitData() && window.WebApp?.shareMaxContent){
  // Called directly from a click, before any await: MAX checks user activation.
  await window.WebApp.shareMaxContent({text:title,link});return 'Выберите получателя в MAX';
 }
 await navigator.clipboard.writeText(link);return 'Ссылка скопирована';
}
