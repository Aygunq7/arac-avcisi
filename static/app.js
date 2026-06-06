let OPTIONS = null;
const $ = id => document.getElementById(id);
function toast(msg){ const t=$('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2600); }
async function api(url,opt={}){ const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt}); const j=await r.json().catch(()=>({ok:false,error:'JSON okunamadı'})); if(!r.ok||j.ok===false) throw new Error(j.error||'İşlem başarısız'); return j; }
function fillSelect(sel, arr, val){ sel.innerHTML=''; arr.forEach(x=>{ const o=document.createElement('option'); o.value=x; o.textContent=x; sel.appendChild(o); }); if(val) sel.value=val; }
async function loadOptions(){ OPTIONS=await api('/api/options?v=24'); fillSelect($('city'), OPTIONS.cities); fillSelect($('fuel'), OPTIONS.fuels); fillSelect($('transmission'), OPTIONS.transmissions, 'Otomatik'); const brands=Object.keys(OPTIONS.vehicles); fillSelect($('brand'), brands, 'Volkswagen'); updateModels(); const s=$('sources'); s.innerHTML=''; Object.entries(OPTIONS.sources).forEach(([key,v])=>{ const lab=document.createElement('label'); lab.className='chip'; lab.innerHTML=`<input type="checkbox" value="${key}" checked> ${v.label}`; s.appendChild(lab); }); }
function updateModels(){ const b=$('brand').value; const models=Object.keys(OPTIONS.vehicles[b]||{}); fillSelect($('model'), models, models.includes('Tiguan')?'Tiguan':models[0]); updateVariants(); }
function updateVariants(){ const b=$('brand').value, m=$('model').value; const vars=(OPTIONS.vehicles[b]&&OPTIONS.vehicles[b][m])||['Farketmez']; fillSelect($('variant'), vars, vars.includes('1.4 TSI Comfortline')?'1.4 TSI Comfortline':vars[0]); }
function formData(){ return {name:$('name').value, city:$('city').value, brand:$('brand').value, model:$('model').value, variant:$('variant').value, brand_custom:$('brand_custom').value, model_custom:$('model_custom').value, variant_custom:$('variant_custom').value, min_year:$('min_year').value, max_year:$('max_year').value, max_km:$('max_km').value, min_price:$('min_price').value, max_price:$('max_price').value, fuel:$('fuel').value, transmission:$('transmission').value, interval_hours:$('interval_hours').value, email:$('email').value, telegram_chat_id:$('telegram_chat_id').value, sources:[...document.querySelectorAll('#sources input:checked')].map(x=>x.value)}; }
async function createSearch(){ const b=$('createBtn'); b.disabled=true; b.textContent='Takip kaydediliyor...'; try{ const j=await api('/api/searches',{method:'POST',body:JSON.stringify(formData())}); toast(j.message||'Takip kaydedildi'); await loadSearches(); }catch(e){ toast(e.message); } finally{ b.disabled=false; b.textContent='Takibi başlat'; }}
function esc(s){return (s??'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function fmtTime(t){ if(!t) return 'henüz yok'; try{return new Date(t).toLocaleString('tr-TR');}catch(e){return t;} }
async function loadSearches(){ const box=$('searches'); const j=await api('/api/searches?v='+Date.now()); if(!j.searches.length){ box.innerHTML='<div class="empty"><b>Henüz takip yok.</b><br>Yukarıdan araç ve site seçip ilk takibi başlat.</div>'; return;} box.innerHTML=''; j.searches.forEach(s=>box.appendChild(renderSearch(s))); }
function renderSearch(s){ const div=document.createElement('div'); div.className='track'; const openBtns=Object.entries(s.open_urls||{}).map(([k,u])=>`<a href="${esc(u)}" target="_blank" rel="noopener"><button class="open">${esc((OPTIONS.sources[k]||{}).label||k)}'de aç</button></a>`).join(''); div.innerHTML=`<h3>${esc(s.name)}</h3><div class="meta"><span class="pill">${esc(s.brand)} ${esc(s.model)}</span><span class="pill">${esc(s.variant)}</span><span class="pill">${esc(s.city)}</span><span class="pill green">${s.active?'Aktif':'Pasif'}</span><span class="pill">${s.interval_hours} saatte bir</span></div><p>Kaynaklar: ${esc((s.sources||[]).map(k=>(OPTIONS.sources[k]||{}).label||k).join(', '))}</p><p>Bulunan ilan: <b>${s.found_count||0}</b></p><p>Son kontrol: ${fmtTime(s.last_checked)}</p><div class="status">${esc(s.last_status||'Bekliyor')}</div><div class="actions">${openBtns}</div><div class="actions"><button onclick="runNow(${s.id})">Şimdi kontrol et</button><button onclick="testSearchNotification(${s.id})">Bildirim testi</button><button onclick="toggle(${s.id})">Aktif/Pasif</button><button onclick="showResults(${s.id})">Listeyi göster</button><button class="danger" onclick="delSearch(${s.id})">Takibi sil</button></div><div class="actions"><select id="int-${s.id}">${[1,2,4,6,12,24].map(h=>`<option value="${h}" ${h==s.interval_hours?'selected':''}>${h} saatte bir</option>`).join('')}</select><button onclick="saveInterval(${s.id})">Süreyi kaydet</button></div><div id="res-${s.id}"></div>`; return div; }
async function runNow(id){ toast('Kontrol başladı. Bu işlem 20-60 sn sürebilir.'); try{ await api(`/api/searches/${id}/run`,{method:'POST'}); toast('Kontrol tamamlandı'); await loadSearches(); await showResults(id);}catch(e){toast(e.message);} }
async function toggle(id){ await api(`/api/searches/${id}/toggle`,{method:'POST'}); await loadSearches(); }
async function delSearch(id){ if(!confirm('Bu takip ve ilanları silinsin mi?')) return; await api(`/api/searches/${id}`,{method:'DELETE'}); await loadSearches(); }
async function saveInterval(id){ const v=$(`int-${id}`).value; await api(`/api/searches/${id}/interval`,{method:'POST',body:JSON.stringify({interval_hours:v})}); toast('Süre kaydedildi'); await loadSearches(); }
async function showResults(id){ const box=$(`res-${id}`); const j=await api(`/api/searches/${id}/results?v=${Date.now()}`); if(!j.results.length){ box.innerHTML='<div class="empty">Henüz gerçek ilan yakalanmadı. Engelli sitelerde “sitede aç” butonunu kullan. Uygulama sahte ilan üretmez.</div>'; return;} box.innerHTML=j.results.map(r=>`<div class="result"><div class="resultTop"><div><h3>${esc(r.title)}</h3><div class="small">${esc(r.source_label)} ${r.year?' • '+r.year:''} ${r.km_text?' • '+r.km_text:''} ${r.city?' • '+esc(r.city):''}</div></div><div class="price">${esc(r.price_text)}</div></div><div class="urlbox"><input readonly value="${esc(r.url)}"><button onclick="copyText('${esc(r.url)}')">Kopyala</button><a href="${esc(r.url)}" target="_blank" rel="noopener"><button class="open">İlana git</button></a></div></div>`).join(''); }
async function loadEvents(){ const box=$('events'); const j=await api('/api/events?v='+Date.now()); if(!j.events.length){ box.innerHTML='<div class="empty">Henüz bildirim yok. Yeni ilan veya fiyat düşüşü olunca burada linkiyle görünür.</div>';return;} box.innerHTML=j.events.map(e=>`<div class="result"><b>${e.event_type==='price_drop'?'Fiyat düştü':'Yeni ilan'}</b> ${esc(e.title)}<br><span class="small">${esc(e.source_label)} • ${esc(e.price_text)} • ${fmtTime(e.created_at)}</span><div class="urlbox"><input readonly value="${esc(e.url)}"><button onclick="copyText('${esc(e.url)}')">Kopyala</button><a href="${esc(e.url)}" target="_blank"><button class="open">İlana git</button></a></div></div>`).join(''); }
function copyText(t){ navigator.clipboard?.writeText(t); toast('Link kopyalandı'); }

function renderNotifyStatus(j){
  const box=$('notifyStatus');
  const rows=[];
  if(j.config){
    rows.push(`<b>Ayar durumu</b>`);
    rows.push(`Telegram token: ${j.config.telegram_token?'var':'yok'}`);
    rows.push(`Telegram chat id env: ${j.config.telegram_chat_id_env?'var':'yok'}`);
    rows.push(`SMTP host: ${j.config.smtp_host?'var':'yok'}`);
    rows.push(`SMTP user: ${j.config.smtp_user?'var':'yok'}`);
    rows.push(`SMTP pass: ${j.config.smtp_pass?'var':'yok'}`);
    rows.push(`Varsayılan mail: ${j.config.default_notify_email?'var':'yok'}`);
  }
  if(j.results){ j.results.forEach(r=>rows.push(`${r.ok?'✅':'❌'} ${r.channel}: ${esc(r.detail)}`)); }
  box.innerHTML=rows.join('<br>') || 'Durum alınamadı';
}
async function testNotification(){
  try{
    const j=await api('/api/notifications/test',{method:'POST',body:JSON.stringify({email:$('test_email').value||$('email').value, telegram_chat_id:$('test_telegram_chat_id').value||$('telegram_chat_id').value})});
    renderNotifyStatus(j); toast(j.ok?'Test bildirimi gönderildi':'Testte eksik/hata var');
  }catch(e){ toast(e.message); }
}
async function loadNotifyStatus(){
  try{ const j=await api('/api/notifications/status?v='+Date.now()); renderNotifyStatus(j); }catch(e){ toast(e.message); }
}
async function testSearchNotification(id){
  try{ const j=await api(`/api/searches/${id}/notify-test`,{method:'POST'}); toast(j.ok?'Takip test bildirimi gönderildi':'Bildirim testinde hata var'); alert((j.results||[]).map(r=>`${r.ok?'✅':'❌'} ${r.channel}: ${r.detail}`).join('
')); }catch(e){toast(e.message);} 
}

$('brand').addEventListener('change', updateModels); $('model').addEventListener('change', updateVariants); $('createBtn').addEventListener('click', createSearch); $('refreshBtn').addEventListener('click', async()=>{await loadSearches(); await loadEvents();}); $('testNotifyBtn').addEventListener('click', testNotification); $('notifyStatusBtn').addEventListener('click', loadNotifyStatus);
(async()=>{try{await loadOptions(); await loadSearches(); await loadEvents(); setInterval(()=>{loadSearches(); loadEvents();},60000);}catch(e){toast('Başlatma hatası: '+e.message);}})();
