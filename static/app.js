let OPTIONS = null;
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function intervalChoices() {
  return (OPTIONS && OPTIONS.interval_choices) ? OPTIONS.interval_choices : [1, 2, 3, 4, 6, 8, 12, 24, 48, 72];
}
function intervalLabel(h) {
  h = Number(h || 4);
  if (h < 24) return `${h} saatte bir`;
  const d = h / 24;
  return Number.isInteger(d) ? `${d} günde bir` : `${h} saatte bir`;
}
function intervalSelectHtml(id, selected) {
  return `<select id="${id}" class="compact-select">` + intervalChoices().map(h =>
    `<option value="${h}" ${Number(selected || OPTIONS.default_interval_hours || 4) === Number(h) ? 'selected' : ''}>${intervalLabel(h)}</option>`
  ).join('') + `</select>`;
}
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3800);
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
  brand.innerHTML = Object.keys(OPTIONS.catalog).map(b => `<option>${esc(b)}</option>`).join('');
  const city = $('city');
  city.innerHTML = OPTIONS.cities.map(c => `<option>${esc(c)}</option>`).join('');
  if (OPTIONS.cities.includes('Kocaeli')) city.value = 'Kocaeli';
  fillModels();

  const interval = $('check_interval_hours');
  interval.innerHTML = intervalChoices().map(h => `<option value="${h}" ${Number(OPTIONS.default_interval_hours || 4) === Number(h) ? 'selected' : ''}>${intervalLabel(h)}</option>`).join('');

  const sources = $('sources');
  sources.innerHTML = OPTIONS.sources.map(s => `
    <label class="source-tile ${s.mode === 'guarded' ? 'guarded' : ''}">
      <input type="checkbox" value="${esc(s.key)}" checked>
      <span>
        <b>${esc(s.name)}</b>
        ${s.mode === 'guarded' ? '<em>Özel mod</em>' : '<em>Direkt mod</em>'}
        ${s.note ? `<small>${esc(s.note)}</small>` : ''}
      </span>
    </label>
  `).join('');
}
function fillModels() {
  const b = $('brand').value;
  const models = OPTIONS.catalog[b] || [];
  $('model').innerHTML = models.map(m => `<option>${esc(m)}</option>`).join('');
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
    check_interval_hours: Number($('check_interval_hours').value || OPTIONS.default_interval_hours || 4),
    email_to: $('email_to').value.trim(),
    telegram_chat_id: $('telegram_chat_id').value.trim()
  };
  $('createBtn').disabled = true;
  $('createBtn').textContent = 'Başlangıç araması yapılıyor...';
  try {
    const res = await api('/api/searches', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    if (res.duplicate) {
      toast(res.message || 'Bu takip zaten var; kopya oluşturmadım.');
    } else {
      toast('Takip oluşturuldu. İlk liste kayıt edildi.');
    }
    await loadSearches();
    await loadEvents();
  } catch(e) {
    toast(e.message);
  } finally {
    $('createBtn').disabled = false;
    $('createBtn').textContent = 'Takibi başlat';
  }
}
function sourceButtonsHtml(s) {
  const links = s.source_links || [];
  if (!links.length) return '';
  return `<div class="source-links">` + links.map(l => `
    <a class="mini-link" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)}'de aç</a>
    ${l.backup_url ? `<a class="mini-link alt" href="${esc(l.backup_url)}" target="_blank" rel="noopener">${esc(l.name)} yedek ara</a>` : ''}
  `).join('') + `</div>`;
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
      <strong>${esc(s.name)}</strong>
      <span class="badge">${esc(s.brand)} ${esc(s.model)}</span>
      <span class="badge">${esc(s.city || 'Tüm Türkiye')}</span>
      <span class="badge ${s.active ? 'ok' : 'off'}">${s.active ? 'Aktif' : 'Pasif'}</span>
      <span class="badge">${intervalLabel(s.check_interval_hours || OPTIONS.default_interval_hours || 4)}</span>
      <small>Kaynaklar: ${esc(s.sources.join(', '))}</small>
      <small>Son kontrol: ${esc(s.last_checked_at || 'Henüz yok')}</small>
      <small>${esc(s.last_status || '')}</small>
      ${sourceButtonsHtml(s)}
      <div class="actions">
        <button class="ghost" onclick="runNow(${s.id})">Şimdi kontrol et</button>
        <button class="ghost" onclick="toggle(${s.id})">Aktif/Pasif</button>
        <button class="ghost" onclick="showItems(${s.id})">Bulunanları göster</button>
        <button class="danger" onclick="deleteSearch(${s.id})">Takibi sil</button>
        <div class="interval-editor">
          ${intervalSelectHtml(`interval-${s.id}`, s.check_interval_hours || OPTIONS.default_interval_hours || 4)}
          <button class="ghost" onclick="updateInterval(${s.id})">Süreyi kaydet</button>
        </div>
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
async function deleteSearch(id) {
  if (!confirm('Bu takibi ve bulunan kayıtlarını silmek istiyor musun?')) return;
  await api(`/api/searches/${id}/delete`, {method:'POST'});
  toast('Takip silindi.');
  await loadSearches();
  await loadEvents();
}
async function updateInterval(id) {
  const value = Number($(`interval-${id}`).value);
  await api(`/api/searches/${id}/interval`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({check_interval_hours: value})
  });
  toast(`Kontrol sıklığı ${intervalLabel(value)} olarak kaydedildi.`);
  await loadSearches();
}
async function showItems(id) {
  const list = await api(`/api/searches/${id}/items`);
  const box = $(`items-${id}`);
  if (!list.length) {
    box.innerHTML = '<div class="item"><strong>Henüz ilan yakalanmadı.</strong><small>Bazı siteler otomatik okumayı engelleyebilir. Bu durumda ilgili sitenin aç butonuyla hazır aramayı telefonundan açabilirsin.</small></div>';
    return;
  }
  box.innerHTML = list.slice(0, 40).map(i => `
    <div class="item">
      <strong>${esc(i.title)}</strong>
      <span class="badge">${esc(i.source_name)}</span>
      <span class="badge">${fmtPrice(i.current_price)}</span>
      ${i.year ? `<span class="badge">${i.year}</span>` : ''}
      ${i.km ? `<span class="badge">${new Intl.NumberFormat('tr-TR').format(i.km)} km</span>` : ''}
      <small><a href="${esc(i.url)}" target="_blank" rel="noopener">İlana git</a></small>
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
      <strong>${e.event_type === 'new' ? 'Yeni ilan' : 'Fiyat düştü'}: ${esc(e.title)}</strong>
      <span class="badge">${esc(e.source_name || '')}</span>
      <span class="badge">${fmtPrice(e.old_price)} → ${fmtPrice(e.new_price)}</span>
      <small>${esc(e.created_at)}</small>
      <small>${esc(e.notification_status || '')}</small>
      <small><a href="${esc(e.url)}" target="_blank" rel="noopener">İlana git</a></small>
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
