import {useEffect,useId,useRef,useState} from 'react';
import type {Event,Match} from './shared/types';
import {dateText} from './shared/filters';
import {safeUrl} from './shared/api';
export function EventCard({event,open,selected,toggle,vote}:{event:Event;open:()=>void;selected?:boolean;toggle?:()=>void;vote?:{selected:boolean;disabled:boolean;label:string;onClick:()=>void}}){
 const source=safeUrl(event.source.url);
 return <article className="card">
  <Poster event={event}/>
  <div className="card-body"><MatchBadge match={event.match}/>{event.is_demo&&<span className="demo-badge">Тестовое событие</span>}<p className="eyebrow">{event.city_name||event.city} · {event.kind==='place'?'Место для посещения · режим работы у источника':event.ends_at&&new Date(event.ends_at).getUTCFullYear()>2100?'Постоянная программа · расписание у источника':event.starts_at&&new Date(event.starts_at)<new Date()&&event.ends_at?'Идёт до '+dateText(event.ends_at):dateText(event.starts_at)}</p>
   <h3><button className="text-button" onClick={open}>{event.title}</button></h3>{event.available_occurrences>1&&<p className="session-count">Ещё сеансов: {event.available_occurrences-1} · даты внутри</p>}<p className="muted">{event.place_name||'Площадка не указана'}</p>
   <p className="price">{event.is_free?'Бесплатно':event.price_text || (event.price_min!==null?`От ${event.price_min} ₽`:'Цена не указана')}</p>
   
   <div className="source">{source?<a href={source} target="_blank" rel="noreferrer">{event.source.name} ↗</a>:event.source.name}</div>
   <div className="card-actions"><button onClick={open}>Подробнее</button>{toggle&&<button aria-pressed={selected} onClick={toggle}>{selected?'В подборке':'В подборку'}</button>}{vote&&<button className="vote" aria-pressed={vote.selected} disabled={vote.disabled} onClick={vote.onClick}>{vote.label}</button>}</div>
  </div>
 </article>;
}
export function Notice({children}:{children:React.ReactNode}){return <div className="notice" role="status">{children}</div>}

export function Poster({event,detail=false}:{event:Event;detail?:boolean}){
 const image=safeUrl(event.image_url),[state,setState]=useState<'loading'|'loaded'|'error'>(image?'loading':'error');const ref=useRef<HTMLImageElement>(null);
 useEffect(()=>{setState(image?(ref.current?.complete?(ref.current.naturalWidth?'loaded':'error'):'loading'):'error')},[event.id,image]);
 return <div className={`cover ${detail?'detail-poster':''} poster-${state}`} aria-busy={state==='loading'}>
  {state==='error'&&<div className="poster-fallback" aria-hidden="true"><small>{event.category_name}</small><strong>{event.title}</strong></div>}
  {state==='loading'&&<div className="poster-skeleton" aria-hidden="true"><span>↗</span></div>}
  {image&&<img ref={ref} key={event.id} src={`/api/v1/events/${event.id}/image`} alt={detail?`Афиша: ${event.title}`:''} loading={detail?'eager':'lazy'} referrerPolicy="no-referrer" onLoad={()=>setState('loaded')} onError={()=>setState('error')}/>}
  <span className="age">{event.age_restriction===null?'Возраст не указан':`${event.age_restriction}+`}</span>
 </div>;
}

export function MatchBadge({match}:{match:Match}){
 const [open,setOpen]=useState(false),ref=useRef<HTMLDivElement>(null),id=useId();
 useEffect(()=>{if(!open)return;const close=(e:PointerEvent)=>{if(!ref.current?.contains(e.target as Node))setOpen(false)};const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false)};document.addEventListener('pointerdown',close);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',escape)}},[open]);
 const percent=match?.percent;
 return <div className="match-badge" ref={ref} onPointerEnter={e=>{if(e.pointerType==='mouse')setOpen(true)}} onPointerLeave={e=>{if(e.pointerType==='mouse')setOpen(false)}}>
  <span>{percent===null||percent===undefined?'—':`${percent}%`}</span><button type="button" className="match-help" aria-label="Почему такой процент совпадения" aria-expanded={open} aria-describedby={open?id:undefined} onClick={()=>setOpen(v=>!v)}>?</button>
  {open&&<div className="match-popover" id={id} role="tooltip"><strong>Совпадение с интересами</strong>{(match?.reasons||['Выберите интересы в профиле, чтобы увидеть совпадение.']).map((reason,i)=><p key={i}>{reason}</p>)}</div>}
 </div>;
}
export function ChatModal({link,close}:{link:string|null;close:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{dialog.current?.showModal();return()=>dialog.current?.close()},[]);
 return <dialog ref={dialog} className="chat-dialog" aria-labelledby="chat-heading" onCancel={e=>{e.preventDefault();close()}} onClick={e=>{if(e.target===e.currentTarget)close()}}><div className="dialog-heading"><h2 id="chat-heading">{link?'Чат события':'Чат пока не создан'}</h2><button aria-label="Закрыть окно чата" onClick={close}>×</button></div><p>{link?'Обсудите планы с другими участниками события.':'Для этого события ещё нет общего чата. Можно создать подборку и отправить её друзьям в MAX.'}</p>{link&&<a className="button primary" href={safeUrl(link)} target="_blank" rel="noreferrer">Открыть чат</a>}<button onClick={close}>Понятно</button></dialog>;
}
