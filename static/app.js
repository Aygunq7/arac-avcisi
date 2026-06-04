let OPTIONS = null;
let OPEN_ITEMS = new Set();
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
  if (!v) return 'Fiyat okunamadı';
  return new Intl.NumberFormat('tr-TR').format(v) + ' TL';
}
function fmtKm(v) {
  if (!v) return '';
  return new Intl.NumberFormat('tr-TR').format(v) + ' km';
}
function fmtDate(v) {
  if (!v) return '';
  try {
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return String(v);
    return d.toLocaleString('tr-TR', {dateStyle:'short', timeStyle:'short'});
  } catch { return String(v); }
}
function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return ''; }
}
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Link kopyalandı.');
  } catch {
    toast('Link kopyalanamadı, elle seçebilirsin.');
  }
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
  fillPackages();

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
  fillPackages();
}
function fillPackages() {
  const b = $('brand').value;
  const m = $('model').value;
  const byBrand = (OPTIONS.package_map && OPTIONS.package_map[b]) ? OPTIONS.package_map[b] : {};
  let packages = byBrand[m] || OPTIONS.default_packages || ['Farketmez'];
  if (!packages.includes('Farketmez')) packages = ['Farketmez', ...packages];
  $('package_name').innerHTML = packages.map(p => `<option>${esc(p)}</option>`).join('');
}
function selectedSources() {
  return [...document.querySelectorAll('#sources input:checked')].map(x => x.value);
}
async function createSearch() {
  const payload = {
    name: $('name').value.trim(),
    brand: $('brand').value,
    model: $('model').value,
    package_name: $('package_name').value,
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
    if (res.id) OPEN_ITEMS.add(Number(res.id));
    if (res.duplicate) {
      toast(res.message || 'Bu takip zaten var; kopya oluşturmadım.');
    } else {
      toast('Takip oluşturuldu. Bulunan liste aşağıda açılıyor.');
    }
    await loadSearches();
    if (res.id) await showItems(Number(res.id), true);
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
function sourceCountsHtml(s) {
  const counts = s.source_item_counts || [];
  if (!counts.length) return '<small>Bulunan ilan: 0</small>';
  return `<small>Bulunan ilan: <b>${Number(s.item_count || 0)}</b> · ` + counts.map(c => `${esc(c.source_name)}: ${Number(c.count || 0)}`).join(' · ') + `</small>`;
}
async function loadSearches() {
  const data = await api('/api/searches');
  const wrap = $('searches');
  if (!data.length) {
    wrap.innerHTML = '<div class="item"><strong>Henüz takip yok.</strong><small>Yukarıdan araç ve siteleri seçip ilk takibi başlat.</small></div>';
    return;
  }
  wrap.innerHTML = data.map(s => `
    <div class="item search-card">
      <strong>${esc(s.name)}</strong>
      <span class="badge">${esc(s.brand)} ${esc(s.model)}</span>
      ${s.package_name && s.package_name !== 'Farketmez' ? `<span class="badge">${esc(s.package_name)}</span>` : ''}
      <span class="badge">${esc(s.city || 'Tüm Türkiye')}</span>
      <span class="badge ${s.active ? 'ok' : 'off'}">${s.active ? 'Aktif' : 'Pasif'}</span>
      <span class="badge">${intervalLabel(s.check_interval_hours || OPTIONS.default_interval_hours || 4)}</span>
      <small>Kaynaklar: ${esc(s.sources.join(', '))}</small>
      ${sourceCountsHtml(s)}
      <small>Son kontrol: ${esc(fmtDate(s.last_checked_at) || 'Henüz yok')}</small>
      <small>${esc(s.last_status || '')}</small>
      ${sourceButtonsHtml(s)}
      <div class="actions">
        <button class="ghost" onclick="runNow(${s.id})">Şimdi kontrol et</button>
        <button class="ghost" onclick="toggle(${s.id})">Aktif/Pasif</button>
        <button class="ghost" onclick="showItems(${s.id})">Listeyi göster</button>
        <button class="danger" onclick="deleteSearch(${s.id})">Takibi sil</button>
        <div class="interval-editor">
          ${intervalSelectHtml(`interval-${s.id}`, s.check_interval_hours || OPTIONS.default_interval_hours || 4)}
          <button class="ghost" onclick="updateInterval(${s.id})">Süreyi kaydet</button>
        </div>
      </div>
      <div id="items-${s.id}" class="results-box"></div>
    </div>
  `).join('');
  for (const id of [...OPEN_ITEMS]) {
    if ($(`items-${id}`)) showItems(id, true).catch(()=>{});
  }
}
async function runNow(id) {
  toast('Kontrol başladı...');
  const res = await api(`/api/searches/${id}/run`, {method:'POST'});
  OPEN_ITEMS.add(Number(id));
  toast(res.status || 'Kontrol bitti');
  await loadSearches();
  await showItems(id, true);
  await loadEvents();
}
async function toggle(id) {
  await api(`/api/searches/${id}/toggle`, {method:'POST'});
  await loadSearches();
}
async function deleteSearch(id) {
  if (!confirm('Bu takibi ve bulunan kayıtlarını silmek istiyor musun?')) return;
  await api(`/api/searches/${id}/delete`, {method:'POST'});
  OPEN_ITEMS.delete(Number(id));
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
function itemCardHtml(i) {
  const fullUrl = i.url || '';
  return `
    <div class="result-card">
      <div class="result-top">
        <div>
          <strong>${esc(i.title)}</strong>
          <small>${esc(hostOf(fullUrl))}</small>
        </div>
        <span class="price-pill">${fmtPrice(i.current_price)}</span>
      </div>
      <div class="result-badges">
        <span class="badge">${esc(i.source_name)}</span>
        ${i.city ? `<span class="badge">${esc(i.city)}</span>` : ''}
        ${i.year ? `<span class="badge">${i.year}</span>` : ''}
        ${i.km ? `<span class="badge">${fmtKm(i.km)}</span>` : ''}
        ${i.lowest_price && i.lowest_price !== i.current_price ? `<span class="badge ok">En düşük: ${fmtPrice(i.lowest_price)}</span>` : ''}
      </div>
      <small>İlk görüldü: ${esc(fmtDate(i.first_seen_at))} · Son görüldü: ${esc(fmtDate(i.last_seen_at))}</small>
      <div class="url-row">
        <code>${esc(fullUrl)}</code>
        <button class="tiny" onclick="copyText('${esc(fullUrl).replace(/'/g, '&#39;')}')">Kopyala</button>
        <a class="mini-link" href="${esc(fullUrl)}" target="_blank" rel="noopener">İlana git</a>
      </div>
    </div>
  `;
}
async function showItems(id, forceOpen=false) {
  const box = $(`items-${id}`);
  if (!box) return;
  if (OPEN_ITEMS.has(Number(id)) && !forceOpen && box.innerHTML.trim()) {
    OPEN_ITEMS.delete(Number(id));
    box.innerHTML = '';
    return;
  }
  OPEN_ITEMS.add(Number(id));
  box.innerHTML = '<div class="item"><strong>Liste yükleniyor...</strong></div>';
  const list = await api(`/api/searches/${id}/items`);
  if (!list.length) {
    box.innerHTML = `<div class="item"><strong>Henüz ilan yakalanmadı.</strong><small>Kaynaklar otomatik okunamadıysa önce <b>Şimdi kontrol et</b> yap. Linkler artık ana sayfa yerine doğru marka/model/paket sayfasına veya site içi aramaya gider.</small></div>`;
    return;
  }
  const groups = new Map();
  for (const i of list) {
    const k = i.source_name || 'Kaynak';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(i);
  }
  box.innerHTML = [...groups.entries()].map(([source, items]) => `
    <div class="source-group">
      <div class="source-group-head">
        <h3>${esc(source)}</h3>
        <span class="badge">${items.length} ilan</span>
      </div>
      ${items.map(itemCardHtml).join('')}
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
      <small>${esc(fmtDate(e.created_at))}</small>
      <small>${esc(e.notification_status || '')}</small>
      <small><a href="${esc(e.url)}" target="_blank" rel="noopener">İlana git</a></small>
    </div>
  `).join('');
}
async function init() {
  OPTIONS = await api('/api/options');
  fillOptions();
  $('brand').addEventListener('change', fillModels);
  $('model').addEventListener('change', fillPackages);
  $('createBtn').addEventListener('click', createSearch);
  $('refreshBtn').addEventListener('click', async () => { await loadSearches(); await loadEvents(); });
  await loadSearches();
  await loadEvents();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
}
init().catch(e => toast(e.message));
