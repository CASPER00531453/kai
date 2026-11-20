/* Casper arayüzü. Python tarafı: window.pywebview.api (casper/api.py). */
"use strict";

const MODELS = [
  ["claude-opus-5-5", "Claude Opus 5.5 (en iyi yorum)"],
  ["claude-sonnet-5-5", "Claude Sonnet 5.5 (dengeli)"],
  ["claude-haiku-5-5", "Claude Haiku 5.5 (en ucuz, hızlı)"],
  ["claude-fable-5-2", "Claude Fable 5.2 (en güçlü, pahalı)"],
];
const PLATFORM = { whatsapp: ["WhatsApp", "wa"], instagram: ["Instagram", "ig"], discord: ["Discord", "dc"] };

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
let api = null;
let state = null;
let currentPerson = null;
let personTab = "summary";

/* ---------- yardımcılar ---------- */

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function md(text) {
  // Küçük, güvenli Markdown: önce kaçır, sonra biçimle.
  const lines = esc(text || "").split("\n");
  let html = "", list = null;
  const inline = s => s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^#{1,3}\s+(.*)/))) { closeList(); html += `<h3>${inline(m[1])}</h3>`; }
    else if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^&gt;\s?(.*)/))) { closeList(); html += `<blockquote>${inline(m[1])}</blockquote>`; }
    else if (!line.trim()) { closeList(); }
    else { closeList(); html += `<p>${inline(line)}</p>`; }
  }
  closeList();
  return html;
}

function when(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function toast(text, error = false) {
  const el = document.createElement("div");
  el.className = "toast" + (error ? " error" : "");
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), error ? 7000 : 3500);
}

async function call(name, ...args) {
  const res = await api[name](...args);
  if (res && typeof res === "object" && !Array.isArray(res) && res.error) {
    toast(res.error, true);
    throw new Error(res.error);
  }
  return res;
}

function fillModels() {
  for (const sel of $$("select[data-setting]")) {
    sel.innerHTML = MODELS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    sel.value = state.settings[sel.dataset.setting] || "claude-opus-5-5";
    sel.onchange = () => call("save_settings", { [sel.dataset.setting]: sel.value }).then(() => toast("Model kaydedildi"));
  }
}

/* ---------- gezinme ---------- */

function show(page) {
  $$("nav.side button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  $$("main > section").forEach(s => s.classList.toggle("active", s.id === "page-" + page));
  if (page === "people") renderPeople();
  if (page === "daily") renderDaily();
  if (page === "memory") renderFacts();
  if (page === "watch") renderWatchFeed();
}

/* ---------- dertleş ---------- */

function addBubble(role, text, pending = false) {
  const el = document.createElement("div");
  el.className = `bubble ${role}` + (pending ? " pending" : "");
  if (role === "assistant" && !pending) { el.classList.add("md"); el.innerHTML = md(text); }
  else el.textContent = text;
  $("#chatLog").appendChild(el);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
  return el;
}

async function loadChat() {
  const items = await call("chat_history");
  $("#chatLog").innerHTML = "";
  if (!items.length) addBubble("assistant", "Selam. Ben Casper. Bugün aklını kurcalayan biri var mı? Önce **Kişiler** sayfasından sohbetlerini yüklersen kimin ne olduğunu daha iyi anlarım.");
  items.forEach(m => addBubble(m.role, m.content));
}

async function sendChat(ev) {
  ev.preventDefault();
  const input = $("#chatInput");
  const text = input.value.trim();
  if (!text) return;
  if (!state.has_key) { toast("Önce Ayarlar'dan Claude API anahtarını ekle.", true); return; }
  input.value = "";
  addBubble("user", text);
  const wait = addBubble("assistant", "Casper düşünüyor…", true);
  $("#chatSend").disabled = true;
  try {
    const res = await call("chat_send", text);
    wait.remove();
    addBubble("assistant", res.reply);
  } catch (e) {
    wait.textContent = "Cevap alınamadı.";
  } finally {
    $("#chatSend").disabled = false;
    input.focus();
  }
}

/* ---------- kişiler ---------- */

async function renderPeople() {
  state.people = await call("list_people");
  const list = $("#peopleList");
  if (!state.people.length) { list.innerHTML = '<div class="muted small">Henüz kimse yok.</div>'; return; }
  list.innerHTML = state.people.map(p => `
    <button class="person-item ${currentPerson && currentPerson.id === p.id ? "active" : ""}" data-id="${p.id}">
      <b>${esc(p.name)}</b>
      <span class="small muted">${esc(p.relation || "ilişki yazılmamış")} · ${p.message_count} mesaj</span>
    </button>`).join("");
  $$(".person-item", list).forEach(b => b.onclick = () => openPerson(+b.dataset.id));
}

async function openPerson(id, tab) {
  currentPerson = await call("get_person", id);
  if (tab) personTab = tab;
  renderPeople();
  renderPerson();
}

function pct(a, b) { return a + b ? Math.round(100 * a / (a + b)) : 0; }

function statBox(k, v, d = "") {
  return `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`;
}

function renderSummary(p) {
  const m = p.metrics || {};
  if (!m.mesaj) return `<div class="empty">Henüz mesaj yok. <b>Ayarlar</b> sekmesinden bu kişiyle olan sohbetini yükle.</div>`;
  const cnt = m.mesaj_sayisi || { ben: 0, o: 0 };
  const st = m.konusmayi_baslatan || { ben: 0, o: 0 };
  const un = m.cevapsiz_kalan_mesaj || { ben: 0, o: 0 };
  const rt = m.medyan_cevap_dakika || {};
  const k = m.kufur || { ben: {}, o: {} };
  const last30 = m.son_30_gun || {}, prev30 = m.onceki_30_gun || {};
  const trend = (last30.ben + last30.o) - (prev30.ben + prev30.o);
  const mins = v => v == null ? "—" : v < 60 ? `${v} dk` : v < 1440 ? `${(v / 60).toFixed(1)} sa` : `${(v / 1440).toFixed(1)} gün`;
  const kufurBar = side => {
    const s = k[side] || {};
    const total = ["temiz", "gündelik", "atışma", "dikkat", "ağır"].reduce((a, x) => a + (s[x] || 0), 0) || 1;
    const seg = (x, c) => `<span style="width:${100 * (s[x] || 0) / total}%;background:${c}"></span>`;
    return `<div class="bar">${seg("temiz", "#3b4256")}${seg("gündelik", "#6c7a96")}${seg("atışma", "var(--warn)")}${seg("dikkat", "#f2994a")}${seg("ağır", "var(--bad)")}</div>
      <div class="small muted" style="margin-top:4px">gündelik ${s["gündelik"] || 0} · atışma ${s["atışma"] || 0} · dikkat ${s["dikkat"] || 0} · ağır ${s["ağır"] || 0}</div>`;
  };
  const twoSided = m.iki_taraf_var;
  return `
    ${twoSided ? "" : `<div class="card small" style="margin-bottom:12px">Bu kişiyle sadece tek tarafın mesajları var (Discord paketinde sadece senin mesajların olur). Bazı ölçümler eksik kalır.</div>`}
    <div class="grid cols-4">
      ${statBox("Toplam mesaj", m.mesaj, `${m.ilk_mesaj} → ${m.son_mesaj}`)}
      ${statBox("Konuşmayı kim başlatıyor", twoSided ? `%${pct(st.ben, st.o)} sen` : "—", `sen ${st.ben} · o ${st.o}`)}
      ${statBox("Mesaj payı", twoSided ? `%${pct(cnt.ben, cnt.o)} sen` : "—", `sen ${cnt.ben} · o ${cnt.o}`)}
      ${statBox("Son mesajdan beri", `${m.son_mesajdan_beri_gun} gün`, "")}
      ${statBox("Senin cevap süren", mins(rt.benim_cevabim), "medyan")}
      ${statBox("Onun cevap süresi", mins(rt.onun_cevabi), "medyan")}
      ${statBox("Cevapsız kalan", `sen ${un.ben} · o ${un.o}`, "24 saat dönüş olmayan mesaj")}
      ${statBox("Son 30 gün", `${(last30.ben || 0) + (last30.o || 0)} mesaj`, `önceki 30 gün: ${(prev30.ben || 0) + (prev30.o || 0)} ${trend > 0 ? "↑" : trend < 0 ? "↓" : ""}`)}
    </div>
    <div class="grid cols-2" style="margin-top:12px">
      <div class="stat"><div class="k">Soru sorma oranı</div><div class="v">sen %${(m.soru_orani_yuzde || {}).ben ?? 0} · o %${(m.soru_orani_yuzde || {}).o ?? 0}</div><div class="d">soru soran, karşısındakiyle ilgilenir</div></div>
      <div class="stat"><div class="k">Ortalama mesaj uzunluğu</div><div class="v">sen ${(m.ortalama_kelime || {}).ben ?? 0} · o ${(m.ortalama_kelime || {}).o ?? 0} kelime</div><div class="d">birden kısalma mesafe işareti olabilir</div></div>
    </div>
    <h2>Küfür ve atışma</h2>
    <p class="small muted" style="margin-top:-4px">amk, aq, lan gibi gündelik kelimeler küfür sayılmaz. Sadece aileye yönelik, tehdit ya da aşağılama içeren ve şaka işareti olmayan mesajlar "dikkat/ağır" olur.</p>
    <div class="grid cols-2">
      <div class="stat"><div class="k">Sen</div>${kufurBar("ben")}</div>
      <div class="stat"><div class="k">${esc(p.name)}</div>${kufurBar("o")}</div>
    </div>`;
}

function renderAnalysis(p) {
  const items = p.analyses || [];
  return `
    <div class="row" style="margin-bottom:12px">
      <button class="btn primary" id="analyzeBtn" ${p.metrics && p.metrics.mesaj ? "" : "disabled"}>Casper'a analiz ettir</button>
      <span class="small muted grow">Bütün sohbet geçmişine, ölçümlere ve bilgi notlarına bakar; kişi kartını da günceller. Uzun sohbetlerde 1 dakika sürebilir.</span>
    </div>
    ${items.length ? items.map(a => `<div class="card md"><div class="small muted">${when(a.ts)}</div>${md(a.text)}</div>`).join("") : '<div class="empty">Henüz analiz yok.</div>'}`;
}

function renderCard(p) {
  return `
    <p class="small muted">Casper'ın bu kişi hakkındaki notları. Analizden sonra kendisi günceller; sen de düzeltebilirsin.</p>
    <textarea id="cardText" style="min-height:260px">${esc(p.card || "")}</textarea>
    <div class="row" style="margin-top:10px"><button class="btn primary" id="cardSave">Kartı kaydet</button></div>`;
}

function renderRecent(p) {
  const msgs = p.recent || [];
  if (!msgs.length) return '<div class="empty">Mesaj yok.</div>';
  return `<div class="msglist">${msgs.map(m => `<div class="${m.from_me ? "me" : ""}"><span class="small muted">${when(m.ts)} · ${esc(m.from_me ? "sen" : m.sender)}</span><br>${esc(m.text)}</div>`).join("")}</div>`;
}

function aliasRow(a = { platform: "", name: "" }) {
  const opts = [["", "her yerde"], ["whatsapp", "WhatsApp"], ["instagram", "Instagram"], ["discord", "Discord"]]
    .map(([v, l]) => `<option value="${v}" ${a.platform === v ? "selected" : ""}>${l}</option>`).join("");
  return `<div class="alias-row"><select class="alias-platform">${opts}</select><input type="text" class="alias-name" value="${esc(a.name)}" placeholder="görünen ad"><button class="btn alias-del" type="button">✕</button></div>`;
}

function renderSettings(p) {
  const counts = (p.platform_counts || []).map(c => `<span class="tag ${PLATFORM[c.platform]?.[1] || ""}">${PLATFORM[c.platform]?.[0] || c.platform}: ${c.n}</span>`).join(" ");
  return `
    <div class="card">
      <h3 style="margin-top:0">Sohbet yükle</h3>
      <p class="small muted">Bu kişiyle olan dışa aktarılmış sohbeti seç. Aynı mesaj iki kez eklenmez, gönül rahatlığıyla tekrar yükleyebilirsin.</p>
      <div class="row">
        <select id="impPlatform" style="max-width:180px">
          <option value="whatsapp">WhatsApp (.txt / .zip)</option>
          <option value="instagram">Instagram (JSON paketi)</option>
          <option value="discord">Discord (veri paketi)</option>
        </select>
        <button class="btn primary" id="impFiles">Dosya seç</button>
        <button class="btn" id="impFolder">Klasör seç</button>
      </div>
      <div id="impPreview" style="margin-top:12px"></div>
      <div style="margin-top:10px">${counts || '<span class="small muted">Henüz mesaj yok.</span>'}</div>
      ${(p.imports || []).length ? `<details style="margin-top:10px"><summary class="small muted">Yükleme geçmişi</summary>${p.imports.map(i => `<div class="small muted">${when(i.ts)} · ${PLATFORM[i.platform]?.[0] || i.platform} · ${esc(i.source)} · +${i.added}</div>`).join("")}</details>` : ""}
    </div>
    <div class="card">
      <h3 style="margin-top:0">Kişi bilgileri</h3>
      <div class="grid cols-2">
        <label class="field">Ad<input type="text" id="pName" value="${esc(p.name)}"></label>
        <label class="field">İlişki<input type="text" id="pRelation" value="${esc(p.relation)}" placeholder="kanka, sınıf arkadaşı…"></label>
      </div>
      <label class="field" style="margin-top:10px">Senin notların (Casper bunları bilir)<textarea id="pNotes" placeholder="Nereden tanışıyorsunuz, aranızda ne oldu…">${esc(p.notes)}</textarea></label>
      <h3>Görünen adları</h3>
      <p class="small muted" style="margin-top:-2px">Sohbetlerde ve ekranda bu kişi hangi adlarla görünüyor? Gözcü modu kişiyi bu adlardan tanır.</p>
      <div id="aliasList">${(p.aliases || []).map(aliasRow).join("")}</div>
      <div class="row"><button class="btn" id="aliasAdd" type="button">+ ad ekle</button><span class="grow"></span><button class="btn primary" id="pSave">Kaydet</button></div>
    </div>
    <div class="card row">
      <select id="delPlatform" style="max-width:200px"><option value="">tüm mesajlar</option><option value="whatsapp">WhatsApp mesajları</option><option value="instagram">Instagram mesajları</option><option value="discord">Discord mesajları</option></select>
      <button class="btn danger" id="delMsgs">Mesajları sil</button>
      <span class="grow"></span>
      <button class="btn danger" id="delPerson">Kişiyi tamamen sil</button>
    </div>`;
}

function renderPerson() {
  const p = currentPerson;
  const pane = $("#personPane");
  if (!p) { pane.innerHTML = '<div class="empty">Soldan bir kişi seç.</div>'; return; }
  const tabs = [["summary", "Özet"], ["analysis", "Casper'ın yorumu"], ["card", "Kişi kartı"], ["recent", "Son mesajlar"], ["settings", "Ayarlar · Sohbet yükle"]];
  const body = { summary: renderSummary, analysis: renderAnalysis, card: renderCard, recent: renderRecent, settings: renderSettings }[personTab](p);
  pane.innerHTML = `
    <div class="row"><div class="grow"><h1>${esc(p.name)}</h1><div class="muted">${esc(p.relation || "ilişki yazılmamış")} · ${p.metrics?.mesaj || 0} mesaj</div></div></div>
    <div class="tabs">${tabs.map(([k, l]) => `<button data-tab="${k}" class="${k === personTab ? "active" : ""}">${l}</button>`).join("")}</div>
    <div>${body}</div>`;
  $$(".tabs button", pane).forEach(b => b.onclick = () => { personTab = b.dataset.tab; renderPerson(); });
  bindPerson(p);
}

function bindPerson(p) {
  const on = (id, fn) => { const el = $("#" + id); if (el) el.onclick = fn; };
  on("analyzeBtn", async ev => {
    if (!state.has_key) { toast("Önce Ayarlar'dan Claude API anahtarını ekle.", true); return; }
    ev.target.disabled = true; ev.target.textContent = "Casper inceliyor…";
    try { await call("analyze", p.id); await openPerson(p.id, "analysis"); toast("Analiz hazır"); }
    catch (e) { ev.target.disabled = false; ev.target.textContent = "Casper'a analiz ettir"; }
  });
  on("cardSave", async () => { await call("update_person", p.id, { card: $("#cardText").value }); toast("Kart kaydedildi"); });
  on("aliasAdd", () => { $("#aliasList").insertAdjacentHTML("beforeend", aliasRow()); bindAliasDelete(); });
  bindAliasDelete();
  on("pSave", async () => {
    const aliases = $$(".alias-row").map(r => ({ platform: $(".alias-platform", r).value, name: $(".alias-name", r).value }));
    await call("update_person", p.id, { name: $("#pName").value, relation: $("#pRelation").value, notes: $("#pNotes").value, aliases });
    toast("Kaydedildi"); openPerson(p.id);
  });
  on("delMsgs", async () => {
    const plat = $("#delPlatform").value;
    if (!confirm(`${p.name} ile ${plat ? PLATFORM[plat][0] + " " : ""}mesajlar silinsin mi?`)) return;
    await call("delete_messages", p.id, plat); toast("Silindi"); openPerson(p.id);
  });
  on("delPerson", async () => {
    if (!confirm(`${p.name} ve bütün mesajları, analizleri silinsin mi? Geri alınamaz.`)) return;
    await call("delete_person", p.id); currentPerson = null; renderPeople(); renderPerson();
  });
  on("impFiles", async () => { const r = await call("pick_files", $("#impPlatform").value); if (r.paths.length) preview(p, r.paths); });
  on("impFolder", async () => { const r = await call("pick_folder"); if (r.paths.length) preview(p, r.paths); });
}

function bindAliasDelete() { $$(".alias-del").forEach(b => b.onclick = () => b.parentElement.remove()); }

async function preview(p, paths) {
  const box = $("#impPreview");
  const platform = $("#impPlatform").value;
  box.innerHTML = '<div class="muted small">Dosyalar okunuyor…</div>';
  let res;
  try { res = await call("import_preview", p.id, platform, paths); }
  catch (e) { box.innerHTML = ""; return; }
  const threads = res.threads;
  const many = threads.length > 1;
  const senders = new Set();
  threads.forEach(t => Object.keys(t.senders).forEach(s => senders.add(s)));
  const first = threads.find(t => t.id === res.best) || threads[0];
  const guess = first.guess_me || "";
  const onlyMine = threads.every(t => t.only_mine);
  box.innerHTML = `
    <div class="card" style="background:var(--bg)">
      ${many ? `<div class="small muted" style="margin-bottom:8px">${threads.length} sohbet bulundu. ${esc(p.name)} ile olanları işaretle:</div>` : ""}
      ${threads.map(t => `
        <label class="thread-row">
          <input type="checkbox" class="impThread" value="${esc(t.id)}" ${t.id === res.best || !many ? "checked" : ""}>
          <span class="grow"><b>${esc(t.title)}</b><br><span class="small muted">${t.count} mesaj · ${when(t.first)} → ${when(t.last)} · ${Object.entries(t.senders).slice(0, 4).map(([s, n]) => `${esc(s)} (${n})`).join(", ")}</span></span>
        </label>`).join("")}
      ${onlyMine ? '<p class="small muted">Discord paketinde sadece senin mesajların var; hepsi "sen" olarak eklenecek.</p>' : `
      <label class="field" style="margin-top:10px">Sen hangisisin?
        <select id="impMe">${[...senders].map(s => `<option value="${esc(s)}" ${s === guess ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label>
      ${guess ? "" : '<p class="small" style="color:var(--warn)">Seni tahmin edemedim, listeden kendi adını seç.</p>'}`}
      <div class="row" style="margin-top:10px"><button class="btn primary" id="impGo">İçe aktar</button><button class="btn" id="impCancel">Vazgeç</button></div>
    </div>`;
  $("#impCancel").onclick = () => box.innerHTML = "";
  $("#impGo").onclick = async () => {
    const ids = $$(".impThread:checked").map(c => c.value);
    if (!ids.length) { toast("En az bir sohbet seç.", true); return; }
    const me = onlyMine ? "(ben)" : $("#impMe").value;
    $("#impGo").disabled = true;
    try {
      const r = await call("import_commit", res.token, p.id, ids, me);
      toast(`${r.added} mesaj eklendi${r.skipped ? `, ${r.skipped} zaten vardı` : ""}.`);
      openPerson(p.id, "summary");
    } catch (e) { $("#impGo").disabled = false; }
  };
}

async function createPerson(ev) {
  ev.preventDefault();
  const name = $("#newPersonName").value.trim();
  if (!name) return;
  const r = await call("create_person", name, $("#newPersonRelation").value.trim(), "");
  $("#newPersonName").value = ""; $("#newPersonRelation").value = "";
  await openPerson(r.id, "settings");
  toast(`${name} eklendi. Şimdi sohbetini yükle.`);
}

/* ---------- gözcü ---------- */

function setWatchUI(st) {
  state.watch = { ...state.watch, ...st };
  const on = !!state.watch.running;
  $("#watchToggle").textContent = on ? "Gözcüyü durdur" : "Gözcüyü başlat";
  $("#watchToggle").classList.toggle("primary", !on);
  $("#watchState").textContent = on ? (state.watch.state || "izliyor") : "Kapalı";
  $("#watchPill").textContent = on ? "👁 Gözcü açık" : "Gözcü kapalı";
  $("#watchPill").classList.toggle("on", on);
  if (state.watch.ocr === false && state.watch.ocr_error) $("#watchOcr").textContent = state.watch.ocr_error + " (OCR olmadan ekran görüntüsü doğrudan Claude'a gider; daha pahalı.)";
}

function feedItem(c) {
  return `<div class="item"><div class="meta">${when(c.ts)} · ${esc(c.app)}${c.person ? " · " + esc(c.person) : c.title ? " · " + esc(c.title) : ""}</div>${md(c.text || c.comment)}</div>`;
}

async function renderWatchFeed() {
  const items = await call("watch_recent");
  const names = Object.fromEntries((state.people || []).map(p => [p.id, p.name]));
  $("#watchFeed").innerHTML = items.length
    ? items.reverse().map(w => feedItem({ ts: w.ts, app: w.app, title: w.title, person: names[w.person_id], text: w.comment })).join("")
    : '<div class="empty">Henüz yorum yok. Gözcüyü başlatıp bir sohbet aç.</div>';
}

function bindWatch() {
  const s = state.settings;
  $("#watchInterval").value = String(s.watch_interval);
  $("#watchCooldown").value = String(s.watch_cooldown);
  $$(".watchApp").forEach(c => c.checked = (s.watch_apps || []).includes(c.value));
  $("#watchAll").checked = !!s.watch_all_windows;
  const scr = $("#overlayScreen");
  scr.innerHTML = `<option value="-1">Otomatik (2. ekran varsa o)</option>` +
    (state.screens || []).map(x => `<option value="${x.index}">Ekran ${x.index + 1} (${x.width}×${x.height})</option>`).join("");
  scr.value = String(s.watch_overlay_screen ?? -1);

  $("#watchInterval").onchange = e => call("save_settings", { watch_interval: +e.target.value });
  $("#watchCooldown").onchange = e => call("save_settings", { watch_cooldown: +e.target.value });
  scr.onchange = e => call("save_settings", { watch_overlay_screen: +e.target.value });
  $$(".watchApp").forEach(c => c.onchange = () => call("save_settings", { watch_apps: $$(".watchApp:checked").map(x => x.value) }));
  $("#watchAll").onchange = e => {
    if (e.target.checked && !confirm("Tüm pencereler izlenecek (kara listedekiler hariç). Emin misin?")) { e.target.checked = false; return; }
    call("save_settings", { watch_all_windows: e.target.checked });
  };
  $("#watchToggle").onclick = async () => setWatchUI(await call(state.watch.running ? "watch_stop" : "watch_start"));
  $("#overlayShow").onclick = () => call("overlay_toggle", true);
  $("#overlayHide").onclick = () => call("overlay_toggle", false);
}

/* ---------- gün sonu ---------- */

async function renderDaily() {
  const items = await call("summaries");
  $("#dailyList").innerHTML = items.length
    ? items.map(s => `<div class="card md" style="margin-top:14px"><div class="small muted">${esc(s.day)}</div>${md(s.text)}</div>`).join("")
    : '<div class="empty">Henüz rapor yok.</div>';
}

function bindDaily() {
  $("#dailyAuto").checked = !!state.settings.daily_auto;
  $("#dailyTime").value = state.settings.daily_time || "23:30";
  $("#dailyAuto").onchange = e => call("save_settings", { daily_auto: e.target.checked });
  $("#dailyTime").onchange = e => call("save_settings", { daily_time: e.target.value });
  $("#dailyNow").onclick = async ev => {
    if (!state.has_key) { toast("Önce Ayarlar'dan Claude API anahtarını ekle.", true); return; }
    ev.target.disabled = true; ev.target.textContent = "Casper yazıyor…";
    try { await call("daily_now"); await renderDaily(); } catch (e) { /* toast gösterildi */ }
    ev.target.disabled = false; ev.target.textContent = "Bugünü şimdi özetle";
  };
}

/* ---------- hafıza ---------- */

async function renderFacts() {
  const items = await call("facts");
  $("#factList").innerHTML = items.length
    ? items.map(f => `<div class="card row"><span class="grow">${esc(f.text)}</span><span class="small muted">${when(f.ts)}</span><button class="btn danger" data-id="${f.id}">Sil</button></div>`).join("")
    : '<div class="empty">Casper henüz senin hakkında bir şey kaydetmedi.</div>';
  $$("#factList button").forEach(b => b.onclick = async () => { await call("delete_fact", +b.dataset.id); renderFacts(); });
}

/* ---------- ayarlar ---------- */

function bindSettings() {
  const s = state.settings;
  $("#dataDir").textContent = state.data_dir;
  $("#version").textContent = "Casper " + state.version;
  $("#keyState").textContent = state.has_key ? "Anahtar kayıtlı (bu Windows kullanıcısına şifreli)." : "Anahtar yok. console.anthropic.com adresinden alabilirsin.";
  $("#myNames").value = (s.my_names || []).join(", ");
  $("#blocklist").value = (s.watch_blocklist || []).join(", ");
  $("#saveKey").onclick = async () => {
    const r = await call("save_api_key", $("#apiKey").value);
    state.has_key = r.has_key; $("#apiKey").value = "";
    $("#keyState").textContent = r.has_key ? "Anahtar kaydedildi." : "Anahtar silindi.";
  };
  $("#testKey").onclick = async ev => {
    ev.target.disabled = true;
    try { const r = await call("test_api"); toast("Claude cevap verdi: " + r.reply); } catch (e) { /* toast */ }
    ev.target.disabled = false;
  };
  $("#myNames").onchange = e => call("save_settings", { my_names: e.target.value.split(",").map(x => x.trim()).filter(Boolean) });
  $("#blocklist").onchange = e => call("save_settings", { watch_blocklist: e.target.value.split(",").map(x => x.trim()).filter(Boolean) });
  $("#openData").onclick = () => call("open_folder", "data");
  $("#openKnowledge").onclick = () => call("open_folder", "knowledge");
  $("#wipe").onclick = async () => {
    if (!confirm("Her şey silinecek. Emin misin?")) return;
    await call("wipe", $("#wipeConfirm").value.trim()); toast("Her şey silindi."); location.reload();
  };
}

/* ---------- Python'dan gelen olaylar ---------- */

window.casperEvent = ev => {
  if (ev.type === "comment") {
    const feed = $("#watchFeed");
    if (feed.querySelector(".empty")) feed.innerHTML = "";
    feed.insertAdjacentHTML("afterbegin", feedItem(ev));
  } else if (ev.type === "state") {
    if (state && state.watch && state.watch.running) { state.watch.state = ev.state; $("#watchState").textContent = ev.state; }
  } else if (ev.type === "watch") {
    setWatchUI(ev);
  } else if (ev.type === "error") {
    toast(ev.text, true);
  } else if (ev.type === "daily") {
    toast("Gün sonu raporun hazır 🌙");
    if ($("#page-daily").classList.contains("active")) renderDaily();
  }
};

/* ---------- başlat ---------- */

async function boot() {
  api = window.pywebview.api;
  state = await call("state");
  fillModels();
  bindWatch();
  setWatchUI(state.watch);
  bindDaily();
  bindSettings();
  $$("nav.side button").forEach(b => b.onclick = () => show(b.dataset.page));
  $("#chatForm").onsubmit = sendChat;
  $("#chatInput").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#chatForm").requestSubmit(); } };
  $("#chatClear").onclick = async () => { if (confirm("Sohbet geçmişi silinsin mi? (Hafızadaki bilgiler kalır.)")) { await call("chat_clear"); loadChat(); } };
  $("#newPerson").onsubmit = createPerson;
  $("#factForm").onsubmit = async e => { e.preventDefault(); const v = $("#factInput").value.trim(); if (!v) return; await call("add_fact", v); $("#factInput").value = ""; renderFacts(); };
  await loadChat();
  if (!state.has_key) { show("settings"); toast("Hoş geldin! Önce Claude API anahtarını ekle."); }
}

if (window.pywebview && window.pywebview.api) boot();
else window.addEventListener("pywebviewready", boot);
