let catalog = null;
const $ = (q, el=document) => el.querySelector(q);
const $$ = (q, el=document) => [...el.querySelectorAll(q)];
function opt(v,t=v){ const o=document.createElement('option'); o.value=v; o.textContent=t; return o; }
function badge(t, ok=false){ const s=document.createElement('span'); s.className='badge'+(ok?' ok':''); s.textContent=t; return s; }
async function api(url, opts={}){ const r=await fetch(url,{cache:'no-store',headers:{'Content-Type':'application/json'},...opts}); const j=await r.json().catch(()=>({ok:false,error:'Sunucudan okunamayan cevap geldi'})); if(!r.ok) throw new Error(j.error||'İşlem başarısız'); return j; }
async function boot(){
  catalog = await api('/api/catalog');
  fillCatalog();
  await loadSearches();
  $('#refresh').onclick = loadSearches;
  $('#brand').onchange = () => { fillModels(); fillPackages(); };
  $('#model').onchange = fillPackages;
  $('#searchForm').onsubmit = createSearch;
  if('serviceWorker' in navigator){ /* v20: service worker kapalı, eski cache temizleniyor */ }
}
function fillCatalog(){
  const city=$('#city'), brand=$('#brand'), sources=$('#sources');
  city.innerHTML=''; catalog.cities.forEach(c=>city.append(opt(c)));
  brand.innerHTML=''; Object.keys(catalog.brands).sort().forEach(b=>brand.append(opt(b)));
  sources.innerHTML=''; catalog.sources.forEach(s=>{ const l=document.createElement('label'); l.className='chip'; l.innerHTML=`<input type="checkbox" value="${s.key}" checked> ${s.name}`; sources.append(l); });
  fillModels(); fillPackages();
}
function fillModels(){
  const b=$('#brand').value, m=$('#model'); m.innerHTML=''; (catalog.brands[b]||[]).forEach(x=>m.append(opt(x)));
}
function fillPackages(){
  const b=$('#brand').value, m=$('#model').value, p=$('#package'); p.innerHTML=''; const list=((catalog.packages[b]||{})[m])||['Farketmez']; list.forEach(x=>p.append(opt(x)));
}
async function createSearch(e){
  e.preventDefault();
  const f=new FormData(e.target);
  const data=Object.fromEntries(f.entries());
  data.sources=$$('#sources input:checked').map(x=>x.value);
  const btn=$('#searchForm button[type=submit]');
  btn.disabled=true;
  $('#formMsg').textContent='Takip kaydediliyor...';
  try{
    const res=await api('/api/searches',{method:'POST',body:JSON.stringify(data)});
    if(!res.ok) throw new Error(res.error || 'Takip kaydedilemedi');
    $('#formMsg').textContent='Takip kaydedildi. Başlangıç araması arkada çalışıyor.';
    e.target.reset(); fillCatalog();
    // Kayıt başarılıysa, liste yükleme hatası artık “işlem başarısız” diye gösterilmez.
    loadSearches().catch(err=>{ $('#formMsg').textContent='Takip kaydedildi ama liste yenilenemedi. Sayfayı yenile.'; });
    setTimeout(()=>loadSearches().catch(()=>{}), 2500);
    setTimeout(()=>loadSearches().catch(()=>{}), 9000);
  }
  catch(err){ $('#formMsg').textContent=err.message||'Takip kaydedilemedi'; }
  finally{ btn.disabled=false; }
}
async function loadSearches(){
  const box=$('#searches'); box.innerHTML='<div class="empty">Yükleniyor...</div>';
  const j=await api('/api/searches'); box.innerHTML='';
  if(!j.searches.length){ box.innerHTML='<div class="empty">Henüz takip yok.</div>'; return; }
  j.searches.forEach(renderSearch);
}
function renderSearch(s){
  const tpl=$('#searchTpl').content.cloneNode(true); const card=$('.search-card',tpl);
  $('h3',card).textContent=s.name||`${s.brand} ${s.model}`;
  const badges=$('.badges',card); badges.append(badge(`${s.brand} ${s.model}`)); badges.append(badge(s.package_name||'Farketmez')); badges.append(badge(s.city||'Tüm Türkiye')); badges.append(badge(s.active?'Aktif':'Pasif', !!s.active)); badges.append(badge(`${s.interval_hours||4} saatte bir`));
  $('.sources',card).textContent='Kaynaklar: '+(s.sources||[]).join(', ');
  $('.date',card).textContent='Son kontrol: '+(s.last_checked_at||'henüz yok');
  $('.status',card).textContent=s.last_status||'İlk arama bekleniyor';
  const links=$('.linkBtns',card);
  Object.entries(s.open_urls||{}).forEach(([k,u])=>{ const src=(catalog.sources||[]).find(x=>x.key===k); const a=document.createElement('a'); a.href=u; a.target='_blank'; a.rel='noopener'; a.textContent=(src?src.name:k)+"'de aç"; links.append(a); });
  $('.run',card).onclick=async()=>{ $('.status',card).textContent='Kontrol ediliyor...'; try{ const r=await api(`/api/searches/${s.id}/run`,{method:'POST',body:'{}'}); $('.status',card).textContent=r.status||r.error||'Kontrol tamamlandı'; await loadItems(s.id, $('.items',card)); }catch(err){ $('.status',card).textContent=err.message||'Kontrol başarısız'; } await loadSearches(); };
  $('.toggle',card).onclick=async()=>{ await api(`/api/searches/${s.id}/toggle`,{method:'POST',body:'{}'}); await loadSearches(); };
  $('.delete',card).onclick=async()=>{ if(confirm('Bu takibi ve kayıtlı ilanları silmek istiyor musun?')){ await api(`/api/searches/${s.id}`,{method:'DELETE'}); await loadSearches(); } };
  $('.show',card).onclick=()=>loadItems(s.id, $('.items',card));
  $('.interval',card).value=String(s.interval_hours||4);
  $('.saveInterval',card).onclick=async()=>{ await api(`/api/searches/${s.id}/interval`,{method:'POST',body:JSON.stringify({check_interval_hours:$('.interval',card).value})}); await loadSearches(); };
  $('#searches').append(tpl);
  countItems(s.id, $('.count',card));
}
async function countItems(id, el){ const j=await api(`/api/searches/${id}/items`); const by={}; j.items.forEach(i=>by[i.source_name]=(by[i.source_name]||0)+1); el.textContent='Bulunan ilan: '+j.items.length+(j.items.length?' | '+Object.entries(by).map(([k,v])=>`${k}: ${v}`).join(', '):''); }
async function loadItems(id, box){
  box.innerHTML='<div class="empty">Liste yükleniyor...</div>'; const j=await api(`/api/searches/${id}/items`); box.innerHTML='';
  if(!j.items.length){ box.innerHTML='<div class="empty">Henüz ilan yakalanmadı. Engel koyan sitelerde “sitede aç” butonunu kullan. Uygulama sahte ilan üretmez.</div>'; return; }
  j.items.forEach(i=>{ const d=document.createElement('div'); d.className='item'; d.innerHTML=`<div class="itemTop"><h3>${esc(i.title)}</h3><span class="price">${esc(i.price_text||'Fiyat yok')}</span></div><div class="meta"><span>${esc(i.source_name)}</span>${i.year?`<span>${i.year}</span>`:''}${i.km_text?`<span>${esc(i.km_text)}</span>`:''}${i.city?`<span>${esc(i.city)}</span>`:''}</div><div class="urlBox"><input readonly value="${esc(i.url)}"><button>Kopyala</button><a class="linkBtns" href="${esc(i.url)}" target="_blank" rel="noopener"><button>İlana git</button></a></div>`; $('button',d).onclick=()=>navigator.clipboard.writeText(i.url); box.append(d); });
}
function esc(x){ return String(x??'').replace(/[&<>"]/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m])); }
boot().catch(e=>{ document.body.insertAdjacentHTML('afterbegin',`<div class="card">Uygulama yüklenemedi: ${esc(e.message)}</div>`); });
