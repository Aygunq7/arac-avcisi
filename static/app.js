let OPTIONS = null;
const $ = (id) => document.getElementById(id);

function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}
function num(id) {
  const v = $(id).value.trim();
  return v ? Number(v) : null;
}
function fmtPrice(v) {
  if (!v) return 'Fiyat yok';
  return new Intl.NumberFormat('tr-TR').format(v) + ' TL';
}
async function api(path, opts={}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.message || 'İşlem başarısız');
  return data;
}
function fillOptions() {
  const brand = $('brand');
  brand.innerHTML = Object.keys(OPTIONS.catalog).map(b => `<option>${b}</option>`).join('');
  const city = $('city');
  city.innerHTML = OPTIONS.cities.map(c => `<option>${c}</option>`).join('');
  if (OPTIONS.cities.includes('Kocaeli')) city.value = 'Kocaeli';
  fillModels();
  const sources = $('sources');
  sources.innerHTML = OPTIONS.sources.map(s => `
    <label class="source-tile"><input type="checkbox" value="${s.key}" checked> <span>${s.name}</span></label>
  `).join('');
}
function fillModels() {
  const b = $('brand').value;
  const models = OPTIONS.catalog[b] || [];
  $('model').innerHTML = models.map(m => `<option>${m}</option>`).join('');
}
function selectedSources() {
  return [...document.querySelectorAll('#sources input:checked')].map(x => x.value);
}
async function createSearch() {
  const payload = {
    name: $('name').value.trim(),
    brand: $('brand').value,
    model: $('model').value,
    city: $('city').value,
    year_min: num('year_min'),
    year_max: num('year_max'),
    price_min: num('price_min'),
    price_max: num('price_max'),
    km_max: num('km_max'),
    fuel: $('fuel').value,
    gear: $('gear').value,
    sources: selectedSources(),
    email_to: $('email_to').value.trim(),
    telegram_chat_id: $('telegram_chat_id').value.trim()
  };
  $('createBtn').disabled = true;
  $('createBtn').textContent = 'Başlangıç araması yapılıyor...';
  try {
    const res = await api('/api/searches', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    toast('Takip oluşturuldu. İlk liste kayıt edildi.');
    await loadSearches();
    await loadEvents();
  } catch(e) {
    toast(e.message);
  } finally {
    $('createBtn').disabled = false;
    $('createBtn').textContent = 'Takibi başlat';
  }
}
async function loadSearches() {
  const data = await api('/api/searches');
  const wrap = $('searches');
  if (!data.length) {
    wrap.innerHTML = '<div class="item"><strong>Henüz takip yok.</strong><small>Yukarıdan araç ve siteleri seçip ilk takibi başlat.</small></div>';
    return;
  }
  wrap.innerHTML = data.map(s => `
    <div class="item">
      <strong>${s.name}</strong>
      <span class="badge">${s.brand} ${s.model}</span>
      <span class="badge">${s.city || 'Tüm Türkiye'}</span>
      <span class="badge">${s.active ? 'Aktif' : 'Pasif'}</span>
      <small>Kaynaklar: ${s.sources.join(', ')}</small>
      <small>Son kontrol: ${s.last_checked_at || 'Henüz yok'}</small>
      <small>${s.last_status || ''}</small>
      <div class="actions">
        <button class="ghost" onclick="runNow(${s.id})">Şimdi kontrol et</button>
        <button class="ghost" onclick="toggle(${s.id})">Aktif/Pasif</button>
        <button class="ghost" onclick="showItems(${s.id})">Bulunanları göster</button>
      </div>
      <div id="items-${s.id}" class="list" style="margin-top:10px"></div>
    </div>
  `).join('');
}
async function runNow(id) {
  toast('Kontrol başladı...');
  const res = await api(`/api/searches/${id}/run`, {method:'POST'});
  toast(res.status || 'Kontrol bitti');
  await loadSearches();
  await loadEvents();
}
async function toggle(id) {
  await api(`/api/searches/${id}/toggle`, {method:'POST'});
  await loadSearches();
}
async function showItems(id) {
  const list = await api(`/api/searches/${id}/items`);
  const box = $(`items-${id}`);
  if (!list.length) {
    box.innerHTML = '<div class="item"><strong>Henüz ilan yakalanmadı.</strong><small>Bazı siteler otomatik okumayı engelleyebilir. Takip yine kayıtlı durur.</small></div>';
    return;
  }
  box.innerHTML = list.slice(0, 30).map(i => `
    <div class="item">
      <strong>${i.title}</strong>
      <span class="badge">${i.source_name}</span>
      <span class="badge">${fmtPrice(i.current_price)}</span>
      ${i.year ? `<span class="badge">${i.year}</span>` : ''}
      ${i.km ? `<span class="badge">${new Intl.NumberFormat('tr-TR').format(i.km)} km</span>` : ''}
      <small><a href="${i.url}" target="_blank" rel="noopener">İlana git</a></small>
    </div>
  `).join('');
}
async function loadEvents() {
  const data = await api('/api/events');
  const wrap = $('events');
  if (!data.length) {
    wrap.innerHTML = '<div class="item"><strong>Henüz bildirim yok.</strong><small>Başlangıç listesinden sonra yeni ilan veya fiyat düşüşü olunca burada görünür.</small></div>';
    return;
  }
  wrap.innerHTML = data.map(e => `
    <div class="item">
      <strong>${e.event_type === 'new' ? 'Yeni ilan' : 'Fiyat düştü'}: ${e.title}</strong>
      <span class="badge">${e.source_name || ''}</span>
      <span class="badge">${fmtPrice(e.old_price)} → ${fmtPrice(e.new_price)}</span>
      <small>${e.created_at}</small>
      <small>${e.notification_status || ''}</small>
      <small><a href="${e.url}" target="_blank" rel="noopener">İlana git</a></small>
    </div>
  `).join('');
}
async function init() {
  OPTIONS = await api('/api/options');
  fillOptions();
  $('brand').addEventListener('change', fillModels);
  $('createBtn').addEventListener('click', createSearch);
  $('refreshBtn').addEventListener('click', async () => { await loadSearches(); await loadEvents(); });
  await loadSearches();
  await loadEvents();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
}
init().catch(e => toast(e.message));
