import {useEffect,useRef,useState} from 'react';
import {api,body} from './shared/api';
import type {Intent,Suggestion} from './shared/types';

export default function SearchBox({query,setQuery,city,nearby,busy,ready,paused,run,preview,openFilters}:{query:string;setQuery:(v:string)=>void;city:string;nearby:boolean;busy:boolean;ready:boolean;paused:boolean;run:(v:string)=>void;preview:(i:Intent)=>void;openFilters:()=>void}){
 const [open,setOpen]=useState(false),[suggestions,setSuggestions]=useState<Suggestion[]>([]),[active,setActive]=useState(-1);
 const box=useRef<HTMLFormElement>(null),input=useRef<HTMLInputElement>(null),revision=useRef(0),previewRef=useRef(preview),locationRef=useRef({city,nearby});previewRef.current=preview;locationRef.current={city,nearby};
 useEffect(()=>{
  const id=++revision.current;setActive(-1);setSuggestions([]);
  if(paused){setOpen(false);return;}
  const timer=setTimeout(()=>{const location=locationRef.current;void api<{intent:Intent;suggestions:Suggestion[]}>('/search/preview',{method:'POST',body:body({text:query,city:location.city,include_nearby:location.nearby})}).then(v=>{if(id===revision.current){setSuggestions(v.suggestions);if(query.trim())previewRef.current(v.intent);}}).catch(()=>{if(id===revision.current)setSuggestions([])});},220);
  return()=>{clearTimeout(timer);revision.current++};
 },[query,paused]);
 useEffect(()=>{const close=(e:PointerEvent)=>{if(!box.current?.contains(e.target as Node))setOpen(false)};document.addEventListener('pointerdown',close);return()=>document.removeEventListener('pointerdown',close)},[]);
 function choose(index:number){setQuery(suggestions[index].text);setActive(-1);setOpen(false);input.current?.focus();}
 return <form id="search-area" ref={box} className="natural search-box" aria-busy={busy||!ready} onSubmit={e=>{e.preventDefault();if(busy||!ready)return;setOpen(false);run(query)}} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setOpen(false)}}>
  <div className="search-label-row"><label htmlFor="natural">Какие у вас планы?</label><button type="button" className="filter-trigger" disabled={!ready} onClick={openFilters} aria-haspopup="dialog">☷ Фильтры</button></div>
  <div className="search-row"><div className="search-input-wrap"><span aria-hidden="true" className="search-icon">⌕</span>
   <input ref={input} id="natural" disabled={!ready} role="combobox" aria-autocomplete="list" aria-expanded={open&&suggestions.length>0} aria-controls="search-suggestions" aria-activedescendant={active>=0&&open?`suggestion-${active}`:undefined} autoComplete="off" value={query} onFocus={()=>setOpen(true)} onChange={e=>{setQuery(e.target.value);setOpen(true)}} placeholder="Концерт в Краснодаре, нас пятеро…" required maxLength={2000}
    onKeyDown={e=>{if(e.key==='Escape'){setOpen(false);setActive(-1)}else if((e.key==='ArrowDown'||e.key==='ArrowUp')&&suggestions.length){e.preventDefault();setOpen(true);setActive(i=>(i+(e.key==='ArrowDown'?1:-1)+suggestions.length)%suggestions.length)}else if(e.key==='Enter'&&open&&active>=0){e.preventDefault();choose(active)}}}/>
   {query&&<button type="button" className="clear-search" disabled={!ready} aria-label="Очистить запрос" onClick={()=>{setQuery('');input.current?.focus()}}>×</button>}
  </div><button className="primary" disabled={busy||!ready}>Найти ↗</button></div>
  {open&&suggestions.length>0&&<div className="search-suggestions" id="search-suggestions" role="listbox" aria-label="Подсказки поиска">
   <p>Можно дополнить запрос</p>{suggestions.map((item,i)=><button key={item.text} id={`suggestion-${i}`} type="button" role="option" aria-selected={active===i} onPointerDown={e=>e.preventDefault()} onClick={()=>choose(i)}><span aria-hidden="true">⌕</span><span>{item.label}</span><span aria-hidden="true">↖</span></button>)}
  </div>}
 </form>;
}
