import type {Filters,Intent} from './types';
export const initialFilters:Filters={city:'msk',include_nearby:false,party_size:'1',budget_total:'',date_from:'',date_to:'',categories:[],interest_categories:[],source:"",venue:"",time_of_day:"",price_match:"from",sort:"date",price_max:'',age_max:'',age_exact:'',kind:'',is_free:false,query:'',show_demo:false};
export function filterQuery(f:Filters,page=1){
 const p=new URLSearchParams({city:f.city,page:String(page),page_size:'20'});
 for(const key of ['date_from','date_to','price_max','age_max','age_exact','kind','query','source','venue','time_of_day','price_match','sort'] as const)if(f[key]!=='')p.set(key,f[key]);
 if(f.include_nearby)p.set('include_nearby','true');
 const caps=[f.price_max===''?null:Number(f.price_max),f.budget_total===''?null:Math.floor(Number(f.budget_total)/Math.max(1,Number(f.party_size)||1))].filter((x):x is number=>x!==null);if(caps.length)p.set('price_max',String(Math.min(...caps)));
 if(f.show_demo)p.set('show_demo','true');
 if(f.is_free)p.set('is_free','true');f.categories.forEach(x=>p.append('categories',x));f.interest_categories.forEach(x=>p.append('interest_categories',x));return p.toString();
}
export function dateText(v:string|null|undefined){if(!v)return 'Дата не указана';const d=new Date(v);return isNaN(d.valueOf())?'Дата не указана':new Intl.DateTimeFormat('ru',{dateStyle:'medium',timeStyle:v.length>10?'short':undefined,timeZone:'Europe/Moscow'}).format(d);}

export function datePreset(kind:string){
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const day=new Date(today+'T12:00:00Z');const add=(n:number)=>new Date(day.valueOf()+n*86400000).toISOString().slice(0,10);
 if(kind==='halfyear'){const end=new Date(day);end.setUTCMonth(end.getUTCMonth()+6);return {date_from:today,date_to:end.toISOString().slice(0,10)}};
 if(kind==='tomorrow')return {date_from:add(1),date_to:add(1)};
 if(kind==='weekend'){const offset=day.getUTCDay()===0?0:(6-day.getUTCDay()+7)%7;return {date_from:add(offset),date_to:add(offset+(day.getUTCDay()===0?0:1))};}
 return {date_from:today,date_to:add(kind==='week'?6:0)};
}
export const scenarios=[
 ['На вечер','На вечер'],['Бесплатно','Бесплатно'],['Вдвоём до 3000 ₽','Вдвоём до 3000 рублей'],
 ['Стендап','Стендап до 3000 рублей'],['В музей вдвоём','В музей со второй половинкой'],
 ['Рэп / хип-хоп','Хочу на рэп концерт'],['Концерты','Концерты'],['Театр','Хочу в театр'],
 ['Выставки','Выставки'],['В эти выходные','В эти выходные'],['Парки','Парки'],
 ['Аттракционы','Парк развлечений с аттракционами'],['Достопримечательности','Достопримечательности'],
 ['Ярмарки','Ярмарки'],['С детьми','С детьми'],['Джаз','Джазовые концерты'],
 ['Экскурсии','Экскурсии'],['Мастер-классы','Мастер-классы']
];

export function filtersFromIntent(i:Intent,base:Filters):Filters{
 return {...initialFilters,city:i.city,include_nearby:i.include_nearby??base.include_nearby,show_demo:base.show_demo,
  date_from:i.date_from||'',date_to:i.date_to||'',time_of_day:i.time_of_day||'',party_size:String(i.party_size||1),
  budget_total:i.budget_total==null?'':String(i.budget_total),price_max:i.budget_per_person==null?'':String(i.budget_per_person),
  age_max:i.age_max==null?'':String(i.age_max),age_exact:i.age_exact==null?'':String(i.age_exact),
  categories:i.categories||[],interest_categories:i.interest_categories||[],is_free:!!i.free_only,
  query:[...(i.performers||[]),...(i.keywords||[])].join(' '),price_match:i.price_match||'from'};
}
