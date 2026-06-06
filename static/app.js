const $ = (q, el=document) => el.querySelector(q);
const $$ = (q, el=document) => [...el.querySelectorAll(q)];
let OPTIONS = null;
let expanded = new Set();

function toast(msg){ const t=$('#toast'); t.textContent=msg; t.style.display='block'; clearTimeout(window.__toast); window.__toast=setTimeout(()=>t.style.display='none',3200); }
function fmtTL(n){ if(!n) return 'Fiyat yok'; return Number(n).toLocaleString('tr-TR')+' TL'; }
function fmt(n){ if(n===null||n===undefined||n==='') return '-'; return Number(n).toLocaleString('tr-TR'); }
function esc(s){ return String(s??'').replace(/[&<>'"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function opt(sel, arr){ sel.innerHTML=''; arr.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o); }); }

async function api(url, opts={}){ const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts}); const j=await r.json().catch(()=>({ok:false,error:'JSON okunamadı'})); if(!r.ok || j.ok===false){ throw new Error(j.error || ('HTTP '+r.status)); } return j; }
async function loadOptions(){ OPTIONS=await api('/api/options'); opt($('#city'), OPTIONS.cities); opt($('#brand'), Object.keys(OPTIONS.brands)); opt($('#fuel'), OPTIONS.fuels); opt($('#transmission'), OPTIONS.transmissions); opt($('#interval_hours'), OPTIONS.intervals.map(x=>`${x}`)); $('#interval_hours').value='4'; renderSources(); updateModels(); }
function renderSources(){ const box=$('#sources'); box.innerHTML=''; OPTIONS.sources.forEach(s=>{ const label=document.createElement('label'); label.className='source-chip'; label.innerHTML=`<input type="checkbox" value="${esc(s.key)}" checked> ${esc(s.name)}`; box.appendChild(label); }); }
function updateModels(){ const b=$('#brand').value; const models=Object.keys(OPTIONS.brands[b]||{}); opt($('#model'), models); updatePackages(); }
function updatePackages(){ const b=$('#brand').value, m=$('#model').value; opt($('#package'), (OPTIONS.brands[b]&&OPTIONS.brands[b][m]) || ['Farketmez']); }

function formData(){
  return {
    name: $('#name').value.trim(), city: $('#city').value, brand: $('#brand').value, model: $('#model').value, package: $('#package').value,
    min_year: $('#min_year').value, max_year: $('#max_year').value, max_km: $('#max_km').value, min_price: $('#min_price').value, max_price: $('#max_price').value,
    fuel: $('#fuel').value, transmission: $('#transmission').value, interval_hours: Number($('#interval_hours').value || 4), email: $('#email').value.trim(), telegram_chat_id: $('#telegram_chat_id').value.trim(),
    sources: $$('#sources input:checked').map(x=>x.value)
  };
}

async function createWatch(e){
  e.preventDefault();
  const btn=$('#submitBtn'); btn.disabled=true; btn.textContent='Takip kaydediliyor...';
  try{ const j=await api('/api/watches',{method:'POST',body:JSON.stringify(formData())}); toast(j.message || 'Takip kaydedildi'); expanded.add(j.id); await loadWatches(); }
  catch(err){ toast('İşlem başarısız: '+err.message); }
  finally{ btn.disabled=false; btn.textContent='Takibi başlat'; }
}

async function loadWatches(){
  const j=await api('/api/watches');
  const list=$('#watchList');
  if(!j.watches.length){ list.innerHTML='<div class="empty"><b>Henüz takip yok.</b><br>Yukarıdan araç ve siteleri seçip ilk takibi başlat.</div>'; }
  else list.innerHTML=j.watches.map(renderWatch).join('');
  const ev=$('#events');
  ev.innerHTML = j.events.length ? j.events.map(x=>`<div class="event"><b>${esc(x.event_type)}</b> ${esc(x.title||'')}<br><span class="small">${esc(x.source||'')} • ${esc(x.created_at||'')}</span></div>`).join('') : '<div class="empty">Henüz bildirim yok. Yeni ilan veya fiyat düşüşü olunca burada görünür.</div>';
  for(const id of expanded){ const div=$(`#items-${id}`); if(div) await loadItems(id); }
}

function srcName(k){ const s=(OPTIONS?.sources||[]).find(x=>x.key===k); return s?s.name:k; }
function renderWatch(w){
  const sources=(w.sources||[]);
  const status=w.checking? 'Kontrol çalışıyor...' : (w.last_status||'Henüz kontrol yok');
  return `<div class="watch-card" id="watch-${w.id}">
    <h3>${esc(w.name || (w.brand+' '+w.model))}</h3>
    <div class="chips"><span class="chip">${esc(w.brand)} ${esc(w.model)}</span><span class="chip">${esc(w.package||'Farketmez')}</span><span class="chip">${esc(w.city||'Tüm Türkiye')}</span><span class="chip good">${w.active?'Aktif':'Pasif'}</span><span class="chip">${w.interval_hours} saatte bir</span></div>
    <div class="watch-meta">
      <div>Kaynaklar: ${sources.map(srcName).map(esc).join(', ')}</div>
      <div>Bulunan ilan: ${w.items_count || w.last_seen_count || 0}</div>
      <div>Son kontrol: ${esc(w.last_checked_at || 'henüz yok')}</div>
      <div>${esc(status)}</div>
    </div>
    <div class="watch-actions">
      ${sources.map(s=>`<a class="open-btn" href="/api/watches/${w.id}/open/${s}" target="_blank">${esc(srcName(s))}'de aç</a>`).join('')}
    </div>
    <div class="watch-actions">
      <button class="secondary" onclick="checkNow(${w.id})">Şimdi kontrol et</button>
      <button class="secondary" onclick="toggleWatch(${w.id})">Aktif/Pasif</button>
      <button class="secondary" onclick="toggleItems(${w.id})">Listeyi göster</button>
      <button class="danger" onclick="deleteWatch(${w.id})">Takibi sil</button>
    </div>
    <div class="watch-actions"><select id="int-${w.id}">${OPTIONS.intervals.map(x=>`<option value="${x}" ${x==w.interval_hours?'selected':''}>${x} saatte bir</option>`).join('')}</select><button class="secondary" onclick="saveInterval(${w.id})">Süreyi kaydet</button></div>
    <div class="items" id="items-${w.id}" style="display:${expanded.has(w.id)?'block':'none'}"></div>
  </div>`;
}
async function checkNow(id){ toast('Kontrol başlatıldı'); await api(`/api/watches/${id}/check`,{method:'POST',body:'{}'}); setTimeout(loadWatches,2500); }
async function toggleWatch(id){ await api(`/api/watches/${id}/toggle`,{method:'POST',body:'{}'}); await loadWatches(); }
async function deleteWatch(id){ if(!confirm('Takip silinsin mi?')) return; await api(`/api/watches/${id}`,{method:'DELETE'}); expanded.delete(id); await loadWatches(); }
async function saveInterval(id){ const h=$(`#int-${id}`).value; await api(`/api/watches/${id}/interval`,{method:'POST',body:JSON.stringify({interval_hours:h})}); toast('Süre kaydedildi'); await loadWatches(); }
async function toggleItems(id){ const div=$(`#items-${id}`); if(!div) return; if(div.style.display==='none'){ expanded.add(id); div.style.display='block'; await loadItems(id); } else { expanded.delete(id); div.style.display='none'; }}
async function loadItems(id){
  const div=$(`#items-${id}`); if(!div) return; div.innerHTML='<div class="empty">Liste yükleniyor...</div>';
  try{ const j=await api(`/api/watches/${id}/items`); if(!j.items.length){ div.innerHTML='<div class="empty">Henüz ilan yakalanmadı. Engel koyan sitelerde “sitede aç” butonunu kullan. Uygulama sahte ilan üretmez.</div>'; return; }
    div.innerHTML=j.items.map(renderItem).join('');
  }catch(e){ div.innerHTML='<div class="empty">Liste alınamadı: '+esc(e.message)+'</div>'; }
}
function renderItem(it){ const meta=[srcName(it.source), it.year, it.km?fmt(it.km)+' km':null, it.city].filter(Boolean).join(' • '); return `<div class="item"><div class="item-head"><div><b>${esc(it.title)}</b><br><span class="small">${esc(meta)}</span></div><div class="price">${esc(fmtTL(it.price))}</div></div><div class="small">İlk görüldü: ${esc(it.first_seen_at||'-')} • Son görüldü: ${esc(it.last_seen_at||'-')}</div><div class="urlbox"><input readonly value="${esc(it.url)}"><button class="secondary" onclick="navigator.clipboard.writeText('${esc(it.url)}'); toast('Link kopyalandı')">Kopyala</button><a class="open-btn" target="_blank" href="${esc(it.url)}">İlana git</a></div></div>`; }

window.addEventListener('load', async()=>{
  try{ await loadOptions(); $('#brand').addEventListener('change', updateModels); $('#model').addEventListener('change', updatePackages); $('#watchForm').addEventListener('submit', createWatch); $('#refreshBtn').addEventListener('click', loadWatches); await loadWatches(); setInterval(loadWatches,60000); }
  catch(e){ toast('Açılış hatası: '+e.message); }
});
