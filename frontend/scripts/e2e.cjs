// Real frontend + real FastAPI + database. No API route stubs.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],slowMo:20});
 const base=process.env.E2E_BASE_URL||'http://127.0.0.1:5173';
 const output=process.env.E2E_OUTPUT||path.join(require('node:os').tmpdir(),'max-e2e');fs.mkdirSync(output,{recursive:true});
 const contexts=[];const errors=[];
 async function user(name){const ctx=await browser.newContext({viewport:{width:390,height:844},permissions:['clipboard-read','clipboard-write']});contexts.push(ctx);await ctx.addInitScript(n=>sessionStorage.setItem('demoUser',n),name);await ctx.route('https://st.max.ru/**',r=>r.fulfill({body:'',contentType:'application/javascript'}));const p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));return p}
 async function onboarding(p){await p.waitForFunction(()=>document.querySelector('.demo-bar'));await p.waitForFunction(()=>{const label=document.querySelector('.header-right button')?.textContent;return label&&label!=='Профиль'});const save=p.getByRole('button',{name:'Сохранить и перейти к афише'});if(await p.getByRole('heading',{name:'То, что интересно именно вам.'}).isVisible()){await save.waitFor();await p.getByLabel('Возрастная группа').selectOption({label:'18–24'});await save.click();}}
 const a=await user('pavel');await a.goto(base);await onboarding(a);
 await a.locator('.card').first().waitFor();assert.equal(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.ok(await a.getByText('KudaGo',{exact:false}).count()>0);
 await a.evaluate(()=>window.scrollTo(0,0));await a.screenshot({path:path.join(output,'mobile-top.png')});await a.screenshot({path:path.join(output,'mobile-real.png'),fullPage:true});
 await a.setViewportSize({width:1440,height:1050});await a.evaluate(()=>window.scrollTo(0,0));await a.screenshot({path:path.join(output,'desktop-top.png')});await a.screenshot({path:path.join(output,'desktop-real.png'),fullPage:true});
 await a.getByLabel('Только тестовые события').check();await a.locator('.demo-badge').first().waitFor();
 await a.locator('#natural').fill('Бесплатно в Москве 2099-01-01');await a.getByRole('button',{name:'Найти по описанию'}).click();
 await a.getByRole('button',{name:/Выбрать любую дату/}).waitFor();await a.getByRole('button',{name:/Выбрать любую дату/}).click();
 await a.locator('.card').first().waitFor();assert.ok(await a.locator('.card').count()>0);
 // Back to all demo sessions for a 5-option choice.
 await a.getByRole('button',{name:'Афиша',exact:true}).click();await a.locator('.card').first().waitFor();
 for(let i=0;i<5;i++)await a.getByRole('button',{name:'+ Сравнить',exact:true}).first().click();
 await a.getByRole('button',{name:'Создать выбор',exact:true}).click();await a.getByRole('button',{name:/Голосовать · 0/}).first().waitFor();
 await a.getByRole('button',{name:/Голосовать · 0/}).first().click();await a.getByRole('button',{name:/✓ Ваш голос · 1/}).waitFor();
 await a.getByRole('button',{name:'Поделиться в MAX'}).click();await a.getByText('Ссылка скопирована',{exact:true}).waitFor();
 const link=await a.locator('a[href*="?choice="]').getAttribute('href');assert.ok(link);
 const b=await user('anya');await b.goto(link.replace('http://localhost:8080',base));await onboarding(b);
 await b.getByRole('button',{name:/Голосовать · 0/}).first().waitFor();await b.getByRole('button',{name:/Голосовать · 0/}).first().click();
 await b.getByText(/Всего голосов: 2/).waitFor();await a.getByRole('button',{name:'Обновить голоса'}).click();await a.getByText(/Всего голосов: 2/).waitFor();
 await a.evaluate(()=>window.scrollTo(0,0));await a.screenshot({path:path.join(output,'choice.png'),fullPage:true});
 await a.getByRole('button',{name:'Подробнее',exact:true}).first().click();await a.getByRole('button',{name:'Отслеживать и напомнить',exact:true}).click();
 await a.getByRole('button',{name:'Отключить отслеживание',exact:true}).waitFor();
 await a.getByRole('button',{name:'Сообщить о неточности'}).click();await a.getByText('Сообщение о неточности сохранено для проверки.').waitFor();
 const downloadPromise=a.waitForEvent('download');await a.getByRole('link',{name:'Добавить в календарь'}).click();const download=await downloadPromise;const file=await download.path();assert.match(fs.readFileSync(file,'utf8'),/BEGIN:VCALENDAR/);
 await a.getByRole('button',{name:'Уведомления',exact:true}).click();
 for(let i=0;i<15;i++){await a.getByRole('button',{name:'Обновить уведомления'}).click();if(await a.getByText(/Показано локально/).count())break;await a.waitForTimeout(300)}
 assert.ok(await a.getByText(/Показано локально/).count()>0);
 await a.getByRole('button',{name:'Отслеживаю',exact:true}).click();await a.getByRole('button',{name:'Подробнее',exact:true}).first().click();await a.getByRole('button',{name:'Отключить отслеживание',exact:true}).click();await a.getByText('Отслеживание отключено',{exact:true}).waitFor();
 await b.reload();await b.locator('.grid').waitFor();
 assert.deepEqual(errors,[]);console.log('PASS E2E: real catalogue, mobile/desktop, onboarding, natural fallback, relaxation, 5 events, 2 users, vote, copy link, tracking/worker, report, ICS, cancellation, reload.');
 for(const ctx of contexts)await ctx.close();await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
