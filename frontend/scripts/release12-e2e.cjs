const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base=process.env.E2E_BASE_URL||'http://localhost:8080',output=process.env.E2E_OUTPUT||'/tmp/max-v12-browser';fs.mkdirSync(output,{recursive:true});
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.setDefaultTimeout(25000);await page.goto(base);await page.locator('.demo-bar').waitFor();
 await page.getByRole('button',{name:'Павел',exact:true}).waitFor();await page.waitForFunction(()=>!document.body.innerText.includes('Загружаем профиль'));
 if(await page.getByRole('heading',{name:'То, что интересно именно вам.'}).isVisible()){
  await page.getByLabel('Возрастная группа').selectOption({label:'18–24'});await page.getByRole('button',{name:'Сохранить и перейти к афише'}).click();
 }
 await page.locator('.card').first().waitFor();assert.equal(await page.locator('.scenarios button').count(),18);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:path.join(output,'mobile-home.png')});
 const seen=[];
 async function search(text){
  await page.locator('#natural').fill(text);const wait=page.waitForResponse(r=>r.url().includes('/search/natural')&&r.request().method()==='POST');await page.getByRole('button',{name:'Найти по описанию'}).click();const data=await (await wait).json();await page.waitForFunction(()=>!document.querySelector('.natural button').disabled);seen.push({text,total:data.total});return data;
 }
 let data=await search('Хочу сводить девушку в музей');assert.ok(data.total>0);assert.ok(data.results.every(x=>x.event.categories.every(c=>['museum','exhibition'].includes(c))));assert.equal(data.intent.party_size,2);
 assert.ok(await page.locator('.clarifications button').count());await page.locator('.section-title').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'mobile-museum.png')});
 // Clarification changes the text and retains the destination and party size.
 let wait=page.waitForResponse(r=>r.url().endsWith('/search/intent'));
 await page.locator('.clarifications').getByRole('button',{name:'В ближайший месяц',exact:true}).click();data=await (await wait).json();assert.equal(data.intent.venue_type,'museum');assert.equal(data.intent.party_size,2);assert.ok(data.intent.date_from);assert.match(await page.locator('#natural').inputValue(),/В ближайший месяц/);await page.waitForFunction(()=>!document.querySelector('.natural button').disabled);
 data=await search('хочу на рэп концерт');assert.ok(data.total>=20);assert.ok(data.results.every(x=>x.event.categories.includes('concert')&&x.event.genres.some(g=>g.slug==='hip-hop')));
 const before=await page.locator('.card').count();await page.locator('.feed-end').scrollIntoViewIfNeeded();await page.waitForFunction(n=>document.querySelectorAll('.card').length>n,before);assert.ok(await page.locator('.card').count()>before);assert.equal(await page.locator('.pagination').count(),0);
 await page.locator('.section-title').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'mobile-rap.png')});
 const open=page.locator('.card').first().getByRole('button',{name:'Подробнее',exact:true});await open.click();await page.locator('.detail-poster').waitFor();const image=page.locator('.detail-poster img');await image.waitFor();await page.waitForFunction(()=>{const i=document.querySelector('.detail-poster img');return i?.complete&&i.naturalWidth>0});
 const current=page.locator('.sessions button[aria-pressed="true"]');assert.equal(await current.isDisabled(),false);await current.click();await page.getByText(/Этот вариант уже выбран/).waitFor();await page.locator('.narrow h1').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'mobile-detail.png')});await page.getByRole('button',{name:'← К афише',exact:true}).click();assert.ok(await page.locator('.card').count()>before);
 data=await search('стенап до 3000');assert.ok(data.total>0);assert.ok(data.intent.corrected_text.includes('стендап'));assert.ok(data.results.every(x=>x.event.categories.includes('stand-up')&&x.event.price_min<=3000));
 for(const label of ['Бесплатно','В музей вдвоём','Ярмарки']){
  const wait=page.waitForResponse(r=>r.url().includes('/search/natural')&&r.request().method()==='POST');await page.locator('.scenarios').getByRole('button',{name:label,exact:true}).click();const sent=(await wait).request().postDataJSON();assert.equal(await page.locator('#natural').inputValue(),sent.text);await page.waitForFunction(()=>!document.querySelector('.natural button').disabled);
 }
 await page.getByRole('button',{name:'Сбросить',exact:true}).click();await page.getByLabel('Маркировка события').selectOption('16');wait=page.waitForResponse(r=>r.url().includes('/events?')&&r.url().includes('age_exact=16'));await page.getByRole('button',{name:'Применить фильтры',exact:true}).click();data=await (await wait).json();assert.ok(data.total>0);assert.ok(data.items.every(x=>x.age_restriction===16));await page.waitForFunction(()=>!document.body.innerText.includes('Загружаем…'));
 for(let i=0;i<5;i++)await page.getByRole('button',{name:'+ Сравнить',exact:true}).first().click();await page.getByRole('button',{name:'Создать выбор',exact:true}).click();await page.locator('.vote').first().waitFor();assert.equal(await page.locator('.vote').count(),5);await page.locator('.vote').last().click();await page.getByText(/Всего голосов: 1/).waitFor();
 await page.getByRole('button',{name:'Афиша',exact:true}).click();await page.getByRole('button',{name:'Очистить',exact:true}).click();await page.getByRole('button',{name:'Сбросить',exact:true}).click();await page.locator('.card').first().waitFor();await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'desktop-home.png')});
 await page.setViewportSize({width:360,height:780});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.match(await page.locator('footer').innerText(),/v1.2.0/);assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify({status:'passed',widths:[360,390,1440],queries:seen,js_errors:errors},null,2));console.log('PASS v1.2 browser: museum/rap/typo, clarification, infinite feed and back navigation, exact age, poster loaded, selected session clickable, 18 chips/input, five choices/vote, responsive widths.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
