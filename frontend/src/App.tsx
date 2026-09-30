import {useEffect,useRef,useState} from 'react';
import {api,body,setToken,safeUrl} from './shared/api';
import {rawInitData,choiceToken,shareChoice} from './shared/max';
import {initialFilters,filterQuery,dateText,filtersFromIntent,scenarios} from './shared/filters';
import type {Auth,Choice,EventDetail,Filters,Meta,Page,SearchResult,Runtime,Notification,Intent,Discovery,Preferences} from './shared/types';
import {EventCard,Notice,Poster,MatchBadge,ChatModal} from './components';
import Profile from './Profile';
import SearchBox from './SearchBox';
import FiltersDialog from './FiltersDialog';
const VERSION='1.3.2';
type Screen='catalog'|'profile'|'tracked'|'detail'|'choice'|'notifications';
export default function App(){
 const [runtime,setRuntime]=useState<Runtime|null>(null),[notifications,setNotifications]=useState<Notification[]>([]),[demoUser,setDemoUser]=useState(sessionStorage.getItem('demoUser')||'pavel');
 const [screen,setScreen]=useState<Screen>('catalog'),[auth,setAuth]=useState<Auth|null>(null),[authError,setAuthError]=useState(''),[authReady,setAuthReady]=useState(false);
 const [meta,setMeta]=useState<Meta|null>(null),[health,setHealth]=useState<'checking'|'ok'|'error'>('checking');
 const [filters,setFilters]=useState<Filters>(initialFilters),[applied,setApplied]=useState<Filters>(initialFilters),[page,setPage]=useState(1);
 const [catalog,setCatalog]=useState<Page|null>(null),[natural,setNatural]=useState<SearchResult|null>(null),[query,setQuery]=useState('');
 const [detail,setDetail]=useState<EventDetail|null>(null),[selected,setSelected]=useState<string[]>([]);
 const [choice,setChoice]=useState<Choice|null>(null),[pendingChoice,setPendingChoice]=useState<string|null>(null),[choiceTitle,setChoiceTitle]=useState('Куда идём вместе');
 const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(''),[info,setInfo]=useState('');
 const [moreLoading,setMoreLoading]=useState(false),[filtersOpen,setFiltersOpen]=useState(false),[toTop,setToTop]=useState(false),[discovery,setDiscovery]=useState<Discovery|null>(null),[ideaPage,setIdeaPage]=useState(0);
 const detailOrigin=useRef<Screen>('catalog');
 const discoverySeed=useRef(String(Date.now())+Math.random());
 const sentinel=useRef<HTMLDivElement>(null),moreLock=useRef(false),catalogKey=useRef(''),catalogScroll=useRef(0);
 const [chat,setChat]=useState<{link:string|null}|null>(null),[previewEnabled,setPreviewEnabled]=useState(true),[reminder,setReminder]=useState(1440);const seq=useRef(0);
 useEffect(()=>{requestAnimationFrame(()=>window.scrollTo({top:screen==='catalog'?catalogScroll.current:0,behavior:'instant'}))},[screen]);
 async function authenticate(config:Runtime,userName=demoUser){
  setAuthReady(false);setAuth(null);setToken(null);++seq.current;setCatalog(null);setNatural(null);setQuery('');setDiscovery(null);
  try{let result:Auth;if(config.demo_mode){result=await api<Auth>('/auth/demo',{method:'POST',body:body({user:userName})});sessionStorage.setItem('demoUser',userName);setDemoUser(userName)}
   else{const raw=rawInitData();if(!raw){setAuthError('Для профиля, голосования и напоминаний откройте приложение из MAX.');return}result=await api<Auth>('/auth/max',{method:'POST',body:body({init_data:raw})})}
   setToken(result.access_token);setAuth(result);if(result.user.home_city){const home={...initialFilters,city:result.user.home_city,include_nearby:result.user.include_nearby};setFilters(home);setApplied(home);catalogKey.current='';}setAuthError('');setSelected([]);setDetail(null);setChoice(null);if(!result.user.onboarding_completed)setScreen('profile');else if(!pendingChoice)setScreen('catalog');
  }catch(e){setAuthError((e as Error).message)}finally{setAuthReady(true)}
 }
 useEffect(()=>{
  let live=true;fetch('/health').then(r=>{if(live)setHealth(r.ok?'ok':'error')}).catch(()=>{if(live)setHealth('error')});
  api<Meta>('/meta').then(v=>{if(live)setMeta(v)}).catch(e=>{if(live)setError(e.message)});
  api<Runtime>('/runtime').then(async v=>{if(!live)return;setRuntime(v);setPendingChoice(choiceToken());await authenticate(v)}).catch(e=>{if(live){setError(e.message);setAuthReady(true)}});
  const expired=()=>{setAuth(null);setAuthError('Сессия завершилась. Войдите снова.');};window.addEventListener('session-expired',expired);
  return()=>{live=false;window.removeEventListener('session-expired',expired)};
 },[]);
 useEffect(()=>{if(!auth)return;const timer=setTimeout(()=>{setToken(null);setAuth(null);setAuthError('Сессия завершилась. Войдите снова.');},auth.expires_in*1000);return()=>clearTimeout(timer)},[auth]);
 useEffect(()=>{if(auth?.user.onboarding_completed&&pendingChoice){void openChoice(pendingChoice);setPendingChoice(null)}},[auth,pendingChoice]);
 useEffect(()=>{
  if(!authReady)return;
  if(screen!=='catalog'&&screen!=='tracked')return;
  if(screen==='catalog'&&natural)return;
  const key=JSON.stringify([applied,auth?.user.id]);
  if(screen==='catalog'&&catalogKey.current===key&&catalog)return;
  const id=++seq.current;setLoading(true);setCatalog(null);setError('');
  api<Page>(screen==='tracked'?'/me/tracked-events':`/events?${filterQuery(applied,1)}`).then(v=>{
   if(id===seq.current){setCatalog(v);setPage(1);catalogKey.current=screen==='catalog'?key:'';}
  }).catch(e=>{if(id===seq.current){setCatalog(null);setError(e.message)}}).finally(()=>{if(id===seq.current)setLoading(false)});
 },[applied,screen,auth?.user.id,natural===null,authReady]);
 useEffect(()=>{if(!authReady)return;let live=true;setDiscovery(null);api<Discovery>(`/discovery?city=${applied.city}&include_nearby=${applied.include_nearby}&seed=${encodeURIComponent(discoverySeed.current)}`).then(v=>{if(live){setDiscovery(v);setIdeaPage(0)}}).catch(()=>{});return()=>{live=false}},[applied.city,applied.include_nearby,auth?.user.id,authReady]);
 useEffect(()=>{const scroll=()=>setToTop(window.scrollY>650);scroll();window.addEventListener('scroll',scroll,{passive:true});return()=>window.removeEventListener('scroll',scroll)},[]);
 const hasMore=screen==='catalog'&&(natural?natural.page*natural.page_size<natural.total:!!catalog&&catalog.page*catalog.page_size<catalog.total);
 async function loadMore(){
  if(!hasMore||busy||loading||moreLock.current)return;moreLock.current=true;setMoreLoading(true);setError('');
  const id=seq.current;
  try{
   if(natural){const v=await api<SearchResult>('/search/intent',{method:'POST',body:body({intent:natural.intent,show_demo:filters.show_demo,page:natural.page+1})});
    if(id===seq.current)setNatural(old=>old?{...v,llm_status:old.llm_status,results:[...old.results,...v.results.filter(x=>!old.results.some(y=>y.event.id===x.event.id))]}:old);
   }else if(catalog){const v=await api<Page>(`/events?${filterQuery(applied,catalog.page+1)}`);
    if(id===seq.current){setCatalog(old=>({...v,items:[...(old?.items||[]),...v.items.filter(x=>!old?.items.some(y=>y.id===x.id))]}));setPage(v.page);}
   }
  }catch(e){if(id===seq.current)setError((e as Error).message)}finally{moreLock.current=false;setMoreLoading(false)}
 }
 useEffect(()=>{
  const target=sentinel.current;if(!target||!hasMore||loading||busy||error)return;
  const observer=new IntersectionObserver(entries=>{if(entries[0].isIntersecting)void loadMore()},{rootMargin:'500px'});
  observer.observe(target);return()=>observer.disconnect();
 },[hasMore,catalog,natural,screen,loading,busy,error]);
 useEffect(()=>{if(screen!=='notifications')return;api<{items:Notification[]}>('/me/notifications').then(v=>setNotifications(v.items)).catch(e=>setError(e.message))},[screen,auth?.user.id]);
 async function action(fn:()=>Promise<void>){setBusy(true);setError('');setInfo('');try{await fn()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 function requireAuth(){if(auth)return true;setError('Для этого действия откройте приложение из MAX и войдите.');return false;}
 function nav(next:Screen){catalogKey.current='';catalogScroll.current=0;if((next==='profile'||next==='tracked'||next==='notifications')&&!requireAuth())return;setNatural(null);setError('');setInfo('');setScreen(next)}
 async function openEvent(id:string){if(screen!=='detail')detailOrigin.current=screen;if(screen==='catalog')catalogScroll.current=window.scrollY;await action(async()=>{const v=await api<EventDetail>(`/occurrences/${encodeURIComponent(id)}`);setDetail(v);setChat(null);setScreen('detail')})}
 async function openChoice(token:string){await action(async()=>{const v=await api<Choice>(`/group-choices/${encodeURIComponent(token)}`);setChoice(v);setScreen('choice')})}
 function toggle(id:string){setSelected(v=>v.includes(id)?v.filter(x=>x!==id):v.length<5?[...v,id]:v)}
 async function runSearch(text:string,context?:Intent){setPreviewEnabled(false);setQuery(context?`${query}. ${text}`:text);catalogScroll.current=0;const id=++seq.current;setLoading(false);await action(async()=>{const result=await api<SearchResult>(`/search/natural?show_demo=${filters.show_demo}`,{method:'POST',body:body({text,city:context?.city||filters.city,include_nearby:filters.include_nearby,...(context?{context}:{})})});if(id===seq.current){setNatural(result);setFilters(filtersFromIntent(result.intent,filters));setScreen('catalog')}})}
 function resetFilters(){const next={...initialFilters,city:auth?.user.home_city||filters.city,include_nearby:auth?.user.include_nearby||false};setFilters(next);return next}
 function clearSearch(){++seq.current;catalogKey.current='';catalogScroll.current=0;setQuery('');setPreviewEnabled(false);setApplied(resetFilters());setNatural(null);setPage(1)}
 function saveProfile(p:Preferences){if(!auth)return;const home={...initialFilters,city:p.home_city||'msk',include_nearby:p.include_nearby};setAuth({...auth,user:{...auth.user,onboarding_completed:true,home_city:p.home_city,include_nearby:p.include_nearby}});setFilters(home);setApplied(home);setNatural(null);catalogKey.current='';setScreen('catalog');setInfo('Предпочтения сохранены')}
 function backToSearch(){window.scrollTo({top:document.getElementById('search-area')?.offsetTop||0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});document.getElementById('natural')?.focus({preventScroll:true})}
 async function createChoice(){if(!requireAuth())return;await action(async()=>{const v=await api<{public_token:string}>('/group-choices',{method:'POST',body:body({title:choiceTitle,occurrence_ids:selected})});const full=await api<Choice>(`/group-choices/${encodeURIComponent(v.public_token)}`);setChoice(full);setScreen('choice')})}
 async function applyIntent(intent:Intent,targetPage=1){const id=++seq.current;setPreviewEnabled(false);setLoading(false);await action(async()=>{const result=await api<SearchResult>('/search/intent',{method:'POST',body:body({intent,show_demo:filters.show_demo,page:targetPage})});if(id===seq.current){setFilters(filtersFromIntent(intent,filters));setNatural(result);setScreen('catalog')}})}

 const events=natural?natural.results.map(x=>x.event):catalog?.items||[];
 const alternatives=natural?.relaxations||catalog?.alternatives||[];
 const showCards=authReady&&!loading&&!busy;
 return <><header><a className="brand" href="/" onClick={e=>{e.preventDefault();nav('catalog')}}><img src="/logo.svg" alt="" width="32" height="32"/> <span className="brand-name">Точка притяжения</span></a><div className="header-right"><span className={'health '+health} title="React → API → PostgreSQL">{health==='ok'?'Сервис доступен':health==='checking'?'Подключение…':'Нет соединения'}</span><button onClick={()=>nav('profile')}>{auth?.user.first_name||'Профиль'}</button></div></header>
 <main><nav aria-label="Разделы">{(['catalog','tracked','profile','notifications'] as const).map((x,i)=><button key={x} aria-current={screen===x?'page':undefined} onClick={()=>nav(x)}>{['Афиша','Отслеживаю','Интересы','Уведомления'][i]}</button>)}</nav>
 {runtime&&runtime.catalog_version!==VERSION&&<Notice>Версии интерфейса и API различаются. Распакуйте весь новый архив и запустите start-demo.</Notice>}
 {authError&&<Notice>{authError} {runtime&&<button onClick={()=>void authenticate(runtime)}>Войти снова</button>}</Notice>}
 {runtime?.demo_mode&&<div className="demo-bar"><span>Локальный просмотр · v{VERSION} · сообщения MAX заменены журналом</span><label>Пользователь<select aria-label="Тестовый пользователь" value={demoUser} onChange={e=>{setPendingChoice(choice?.public_token||null);void authenticate(runtime,e.target.value)}}><option value="pavel">Павел</option><option value="anya">Аня</option></select></label></div>}
 {error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')} aria-label="Закрыть ошибку">×</button></div>}{info&&<Notice>{info}</Notice>}
 {screen==='profile'&&auth&&<Profile key={auth.user.id} meta={meta} saved={saveProfile}/>}
 {(screen==='catalog'||screen==='tracked')&&<>
  <section className="hero"><div><p className="eyebrow">МОСКВА И КРАСНОДАР / ЖИВЫЕ ВПЕЧАТЛЕНИЯ</p><h1>{screen==='tracked'?'Не пропустите важное':'Хороший повод выйти из дома.'}</h1><p>{screen==='tracked'?'Ваши события и напоминания.':'Найдите событие по настроению. Позовите друзей. Решите вместе.'}</p></div><div className="hero-mark" aria-hidden="true">↗<span>ПЛАНЫ<br/>НА ВЕЧЕР</span></div></section>
  {screen==='catalog'&&<>
   <SearchBox query={query} setQuery={text=>{setPreviewEnabled(true);setQuery(text)}} city={filters.city} nearby={filters.include_nearby} busy={busy} ready={authReady} paused={!authReady||filtersOpen||busy||!previewEnabled} run={text=>void runSearch(text)} preview={intent=>setFilters(current=>filtersFromIntent(intent,current))} openFilters={()=>{setPreviewEnabled(false);setFiltersOpen(true)}}/>
   <div className="search-tools"><button className="location-trigger" disabled={!authReady} onClick={()=>{setPreviewEnabled(false);setFiltersOpen(true)}}><svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg> {meta?.cities.find(c=>c.slug===filters.city)?.label||'Город'}{filters.include_nearby?' и рядом':''}</button>{(natural||query)&&<button className="reset-search" onClick={clearSearch}>Сбросить</button>}</div>
   <FiltersDialog open={filtersOpen} close={()=>setFiltersOpen(false)} filters={filters} setFilters={setFilters} meta={meta} reset={resetFilters} apply={()=>{setPreviewEnabled(false);setQuery('');++seq.current;catalogKey.current='';catalogScroll.current=0;setNatural(null);setPage(1);setApplied({...filters})}}/>
   <div className="ideas-heading"><span>Есть идея</span><button type="button" onClick={()=>setIdeaPage(p=>p+1)}>Ещё идеи ↻</button></div>
   <div className="chips scenarios">{(discovery?.ideas.length?Array.from({length:Math.min(18,discovery.ideas.length)},(_,i)=>discovery.ideas[(ideaPage*11+i)%discovery.ideas.length]):scenarios.map(([label,text])=>({label,text}))).map(item=><button key={item.label} disabled={busy||!authReady} onClick={()=>void runSearch(item.text)}>{item.label}</button>)}</div>
   {showCards&&!natural&&!query&&JSON.stringify(applied)===JSON.stringify({...initialFilters,city:applied.city,include_nearby:applied.include_nearby})&&discovery?.highlights.length? <section className="inspiration"><div className="ideas-heading"><h2>{discovery.highlight_label}</h2></div><div className="inspiration-list">{discovery.highlights.map(event=><article className="inspiration-card" key={event.id}><MatchBadge match={event.match}/><span>{event.category_name}</span><strong><button className="text-button" onClick={()=>void openEvent(event.occurrence_id)}>{event.title}</button></strong><small>{event.city_name} · {event.kind==='place'?'Место для посещения':dateText(event.starts_at)}</small><span className="inspiration-arrow" aria-hidden="true">↗</span></article>)}</div></section>:null}
  </>}
  <div className="section-title"><h2>{natural?'По вашим планам':screen==='tracked'?'Вы отслеживаете':'Ближайшие события'}</h2></div>
  {(!authReady||busy||loading)&&<p role="status">Ищем подходящие впечатления…</p>}
  {authReady&&!loading&&!busy&&!error&&events.length===0&&<section className="empty"><span aria-hidden="true">⌕</span><h2>{screen==='tracked'?'Вы пока ничего не отслеживаете':'Подходящих событий пока нет'}</h2><p>Попробуйте другой день, категорию или бюджет.</p><div className="chips"></div><button onClick={()=>{clearSearch();setScreen('catalog')}}>Открыть весь каталог</button></section>}
  <div className="grid">{showCards&&events.map(event=><EventCard key={event.occurrence_id} event={event} open={()=>void openEvent(event.occurrence_id)} selected={selected.includes(event.occurrence_id)} toggle={()=>toggle(event.occurrence_id)}/>)}</div>
  {showCards&&!error&&screen==='catalog'&&events.length===0&&alternatives.length>0&&<section className="alternatives"><h2>Можно попробовать иначе</h2>{alternatives.map((group,i)=><section key={i}><div className="alternative-heading"><div><h3>{group.label}</h3><p className="muted">{group.explanation}</p></div><button onClick={()=>void applyIntent(group.intent)}>Показать все</button></div><div className="grid">{group.events.map(event=><EventCard key={event.occurrence_id} event={event} open={()=>void openEvent(event.occurrence_id)} selected={selected.includes(event.occurrence_id)} toggle={()=>toggle(event.occurrence_id)}/>)}</div></section>)}</section>}
  {screen==='catalog'&&<div className="feed-end" ref={sentinel}>{hasMore?<button disabled={loading||busy||moreLoading} onClick={()=>void loadMore()}>{moreLoading?'Загружаем ещё…':'Показать ещё'}</button>:events.length>0&&<p>Вы дошли до конца подборки.</p>}</div>}
  {selected.length>0&&<aside className="selection"><div><strong>Совместный выбор · {selected.length}/5</strong><p>Выберите от 2 до 5 разных событий из каталога.</p></div><input aria-label="Название совместного выбора" value={choiceTitle} maxLength={100} onChange={e=>setChoiceTitle(e.target.value)}/><button className="primary" disabled={selected.length<2||busy||!choiceTitle.trim()} onClick={()=>void createChoice()}>Создать выбор</button><button onClick={()=>setSelected([])}>Очистить</button></aside>}
 </>}
 {screen==='detail'&&detail&&<section className="narrow"><button onClick={()=>setScreen(detailOrigin.current)}>{detailOrigin.current==='choice'?'← К подборке':'← К афише'}</button><p className="eyebrow">{detail.city_name}</p><h1>{detail.title}</h1><Poster event={detail} detail/><MatchBadge match={detail.match}/>{detail.is_demo&&<Notice>Тестовые данные. Это не настоящее мероприятие.</Notice>}<p className="muted">{detail.organizers.map(o=>o.name).join(' · ')}</p><p>{detail.kind==='place'?'Место для посещения':dateText(detail.starts_at)}{detail.schedule_kind==='period'&&detail.ends_at?' — '+dateText(detail.ends_at):''} · {detail.place_name||'Площадка не указана'}</p><p className="price">{detail.price_text||'Цена не указана'}</p><p>Возраст: {detail.age_restriction===null?'не указан':`${detail.age_restriction}+`}</p><p>{detail.address||'Адрес не указан'}</p><p className="description">{detail.description||'Описание отсутствует в источнике.'}</p>
  <h2>{detail.kind==='place'?'Посещение':'Даты и сеансы'}</h2>{detail.kind==='place'?<Notice>{detail.schedule_note||'Часы работы уточняйте у площадки.'} Для места не указан отдельный сеанс.</Notice>:<><p className="muted">{detail.occurrences.length===1?'Доступен один вариант — он уже выбран.':'Выберите дату: отслеживание будет относиться к этому сеансу.'}{detail.schedule_kind==='period'?' Источник указал период проведения; точное время посещения уточняйте по ссылке.':''}</p><ul className="sessions">{detail.occurrences.map(x=><li key={x.occurrence_id}><button aria-pressed={x.occurrence_id===detail.occurrence_id} disabled={busy} onClick={()=>{if(x.occurrence_id!==detail.occurrence_id)void openEvent(x.occurrence_id);else setInfo('Этот вариант уже выбран. Можно открыть билеты или включить отслеживание.')}}>{dateText(x.starts_at)}{x.schedule_kind==='period'&&x.ends_at?' — '+dateText(x.ends_at):''} · {x.place_name||'Без площадки'} · {x.occurrence_id===detail.occurrence_id?'✓ Выбран':'Выбрать'}</button></li>)}</ul></>}
  <p><a className="button primary" href={safeUrl(detail.source.url)} target="_blank" rel="noreferrer">{detail.kind==='place'?'Часы работы и условия посещения ↗':'Билеты и расписание у источника ↗'}</a></p><p className="source"><a href={safeUrl(detail.source.url)} target="_blank" rel="noreferrer">{detail.source.name} ↗</a> Проверено: {dateText(detail.source.fetched_at)} · {detail.source.updated_at?'Изменено: '+dateText(detail.source.updated_at):'Время изменения в источнике не указано'}</p>
  {detail.kind!=='place'&&<label>Напомнить до начала<select value={reminder} onChange={e=>setReminder(Number(e.target.value))}><option value={60}>За час</option><option value={180}>За 3 часа</option><option value={1440}>За сутки</option></select></label>}
  <button className="primary" disabled={busy||(!detail.is_tracked&&(detail.status!=='ACTIVE'||detail.kind!=='place'&&new Date(detail.ends_at||detail.starts_at||'')<new Date()))} onClick={()=>{if(!requireAuth())return;void action(async()=>{await api(`/me/tracked-events/${detail.occurrence_id}`,{method:detail.is_tracked?'DELETE':'PUT',...(detail.is_tracked?{}:{body:body({remind_before_minutes:reminder})})});setDetail({...detail,is_tracked:!detail.is_tracked});setChat(null);setInfo(detail.is_tracked?'Отслеживание отключено':detail.kind==='place'?'Место сохранено. Оно доступно в разделе «Отслеживаю».':runtime?.demo_mode?'Сеанс добавлен. Подтверждение появится в разделе уведомлений.':'Сеанс добавлен. Подтверждение отправит бот.')})}}>{detail.is_tracked?'Отключить отслеживание':detail.kind==='place'?'Сохранить место':'Отслеживать и напомнить'}</button>
  <div className="toolbar"><button disabled={busy} onClick={()=>{if(!requireAuth())return;void action(async()=>{const v=await api<{invite_link:string|null}>(`/occurrences/${detail.occurrence_id}/community`);setChat({link:safeUrl(v.invite_link)||null})})}}>Найти чат события</button></div>

 </section>}
 {screen==='choice'&&choice&&<section><p className="eyebrow">РЕШАЕМ ВМЕСТЕ</p><h1>{choice.title}</h1><p>{choice.status==='active'?'Можно выбрать несколько событий. Повторное нажатие отменяет голос.':'Голосование завершено.'} {!choice.results_visible&&'Результаты появятся после вашего выбора.'}</p><div className="toolbar"><button onClick={()=>void action(async()=>{setInfo(await shareChoice(choice.title,choice.deep_link||choice.web_link))})}>Поделиться в MAX ↗</button><button disabled={busy} onClick={()=>void openChoice(choice.public_token)}>Обновить голоса</button></div><p className="muted"><a href={safeUrl(choice.deep_link||choice.web_link)}>{choice.deep_link||choice.web_link}</a></p><div className="grid">{choice.events.map(x=><EventCard key={x.event.occurrence_id} event={x.event} open={()=>void openEvent(x.event.occurrence_id)} vote={{selected:choice.my_votes.includes(x.event.occurrence_id),disabled:busy||choice.status!=='active',label:choice.results_visible?`Проголосовало ${x.votes??0} ${((x.votes??0)%10>=2&&(x.votes??0)%10<=4&&!((x.votes??0)%100>=12&&(x.votes??0)%100<=14))?'человека':'человек'}`:'Голосовать',onClick:()=>{if(!requireAuth())return;void action(async()=>{const selected=choice.my_votes.includes(x.event.occurrence_id);setChoice(await api<Choice>(`/group-choices/${choice.public_token}/${selected?`votes/${x.event.occurrence_id}`:'vote'}`,selected?{method:'DELETE'}:{method:'PUT',body:body({occurrence_id:x.event.occurrence_id})}))})}}}/>)}</div></section>}
 {screen==='notifications'&&<section><h1>Подтверждения и напоминания</h1><p className="muted">{runtime?.demo_mode?'Здесь видны локальные уведомления. Сообщения в MAX не отправляются.':'История отправки и расписание уведомлений бота.'}</p><button onClick={()=>void action(async()=>setNotifications((await api<{items:Notification[]}>('/me/notifications')).items))}>Обновить уведомления</button>{notifications.length===0&&<Notice>Начните отслеживать сеанс, чтобы получить подтверждение.</Notice>}<div className="notification-list">{notifications.map(n=><article key={n.id}><strong>{n.type==='tracking_confirmation'?'Подтверждение':'Напоминание'}</strong><h3>{n.event.title}</h3><p>{dateText(n.scheduled_at)} · {{pending:'Запланировано',processing:'Обрабатывается',preview:'Показано локально',sent:'Отправлено в MAX',cancelled:'Отменено',failed:'Ошибка отправки',review:'Требуется проверка доставки'}[n.status]||n.status}</p><button onClick={()=>void openEvent(n.event.occurrence_id)}>Открыть сеанс</button></article>)}</div></section>}
 {screen==='catalog'&&toTop&&<button className="back-to-search" onClick={backToSearch} aria-label="Вернуться к поиску">↑ <span>К поиску</span></button>}
 {chat&&<ChatModal link={chat.link} close={()=>setChat(null)}/>}
 <footer>Точка притяжения · Афиша в MAX · v{VERSION}<span>Время событий — московское. Данные и билеты — у первоисточника.</span></footer></main></>;
}
