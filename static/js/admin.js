/* Panel de gestión: resumen, visitas/carritos, pedidos, productos, portada y ajustes. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => "$" + Math.round(v || 0).toLocaleString("es-AR");
  const plural = (n, a, b) => `${n} ${n === 1 ? a : b}`;
  const toDate = (s) => new Date(s.replace(" ", "T"));
  const hhmm = (d) => d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
  function when(s) {
    const d = toDate(s), now = new Date(), days = Math.floor((new Date(now.toDateString()) - new Date(d.toDateString())) / 864e5);
    if (days === 0) return "Hoy " + hhmm(d);
    if (days === 1) return "Ayer " + hhmm(d);
    return d.toLocaleDateString("es-AR", { day: "numeric", month: "short" }) + " " + hhmm(d);
  }
  const toast = (m) => { const t = $("#toast"); t.textContent = m; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2600); };
  async function api(url, opts = {}) {
    const r = await fetch(url, { headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opts });
    if (r.status === 401) { showLogin(); throw new Error("Tu sesión venció. Entrá de nuevo."); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Revisá los datos: hay algún campo que no está bien.");
    return data;
  }
  const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  let days = 30, month = null, statusFilter = "", products = [], cats = [], settings = {}, editing = null;
  let pending = [];  // fotos elegidas antes de que la prenda exista: se suben al guardar

  // ------------------------------------------------ login
  function showLogin() { $("#login").hidden = false; $("#pinGate").hidden = true; $("#app").hidden = true; }
  function showGate() { $("#login").hidden = true; $("#pinGate").hidden = false; $("#app").hidden = true; }
  $("#loginForm").onsubmit = async (e) => {
    e.preventDefault(); $("#loginErr").hidden = true;
    try { const r = await api("/api/admin/login", { method: "POST", body: JSON.stringify({ pin: $("#pin").value }) }); $("#pin").value = ""; r.must_change_pin ? showGate() : start(); }
    catch (ex) { $("#loginErr").textContent = ex.message; $("#loginErr").hidden = false; }
  };
  $("#pinGateForm").onsubmit = async (e) => {
    e.preventDefault(); const err = $("#gateErr"); err.hidden = true;
    if ($("#gateNew").value !== $("#gateRepeat").value) { err.textContent = "Los dos PIN no coinciden."; err.hidden = false; return; }
    try { await api("/api/admin/pin", { method: "POST", body: JSON.stringify({ new_pin: $("#gateNew").value }) }); toast("PIN guardado"); start(); }
    catch (ex) { err.textContent = ex.message; err.hidden = false; }
  };
  $("#logout").onclick = async () => { await api("/api/admin/logout", { method: "POST" }).catch(() => {}); showLogin(); };

  // ------------------------------------------------ pestañas
  const LOADERS = { resumen: loadStats, pedidos: loadOrders, productos: loadProducts, portada: loadHome, ajustes: loadSettings };
  $$("[data-tab]").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  function showTab(name) {
    $$("[data-tab]").forEach(b => b.classList.toggle("on", b.dataset.tab === name));
    $$("[data-panel]").forEach(p => p.hidden = p.dataset.panel !== name);
    scrollTo({ top: 0 });
    LOADERS[name]().catch(ex => toast(ex.message));
  }

  // ------------------------------------------------ resumen
  $$("#daysSeg button").forEach(b => b.onclick = () => {
    $$("#daysSeg button").forEach(x => x.classList.toggle("on", x === b));
    if (b.dataset.d === "month") { month = $("#monthSel").value || new Date().toISOString().slice(0, 7); $("#monthSel").hidden = false; }
    else { month = null; days = +b.dataset.d; $("#monthSel").hidden = true; }
    loadStats();
  });
  $("#monthSel").onchange = () => { month = $("#monthSel").value; loadStats(); };
  function fillMonths(first) {
    const sel = $("#monthSel"); if (sel.options.length) return;
    let y = new Date().getFullYear(), m = new Date().getMonth() + 1; const [fy, fm] = first.split("-").map(Number);
    for (let i = 0; i < 36; i++) { sel.insertAdjacentHTML("beforeend", `<option value="${y}-${String(m).padStart(2, "0")}">${MESES[m - 1]} ${y}</option>`); if (y === fy && m === fm) break; if (--m === 0) { m = 12; y--; } }
  }
  function setPending(n) { $("#pendingPill").textContent = n; $("#pendingPill").hidden = !n; $("#pendingDot").hidden = !n; }

  async function loadStats() {
    const s = await api(month ? `/api/admin/stats?month=${month}` : `/api/admin/stats?days=${days}`);
    fillMonths(s.first_month);
    setPending(s.pending.n);
    const ob = s.orders_by_status, nOrders = Object.entries(ob).filter(([k]) => k !== "cancelado").reduce((a, [, v]) => a + v.n, 0);
    const carts = s.funnel.find(f => f.key === "add_to_cart").n;
    $("#kpis").innerHTML = [
      ["Personas que entraron", s.visitors, `${s.new_visitors} por primera vez`],
      ["Armaron un carrito", carts, s.carts_open.n ? `${plural(s.carts_open.n, "quedó", "quedaron")} sin pedido (${money(s.carts_open.total)})` : "ninguno quedó colgado", "hi"],
      ["Pedidos", nOrders, s.pending.n ? `${plural(s.pending.n, "pendiente", "pendientes")} · ${money(s.pending.total)}` : "ninguno pendiente", "hi"],
      ["Ventas confirmadas", money(s.revenue_confirmed), `${(ob.confirmado?.n || 0) + (ob.entregado?.n || 0)} confirmados o entregados`],
    ].map(([l, v, e, c]) => `<div class="kpi ${c || ""}"><small>${l}</small><b>${v}</b><em>${e}</em></div>`).join("");

    const top = Math.max(1, s.funnel[0].n);
    $("#funnel").innerHTML = s.funnel.map(f => `<div class="fstep"><span>${f.label}</span><b>${f.n}<em>${Math.round(f.n / top * 100)}%</em></b><div class="fbar"><i style="width:${f.n / top * 100}%"></i></div></div>`).join("");

    const tot = s.sources.reduce((a, x) => a + x.n, 0) || 1;
    $("#sources").innerHTML = s.sources.length ? s.sources.slice(0, 7).map(x => `<div class="hbar"><span>${esc(x.source)}</span><div><i style="width:${x.n / tot * 100}%"></i></div><b>${Math.round(x.n / tot * 100)}%</b></div>`).join("") : `<p class="muted">Todavía no hay visitas en este período.</p>`;
    const dv = s.devices, dt = (dv.Celular || 0) + (dv.Compu || 0);
    $("#devices").textContent = dt ? `${Math.round((dv.Celular || 0) / dt * 100)}% entra desde el celular` : "";

    drawChart(s.daily);

    const ab = await api(`/api/admin/visitors?days=${month ? 90 : days}&filter=abandoned`);
    $("#abandonedMini").innerHTML = ab.length ? `<div class="mini">${ab.slice(0, 5).map(v => `<div class="mini-row" data-sid="${esc(v.session_id)}"><span>${v.cart_items.map(i => esc(i.name) + (i.size ? ` (${esc(i.size)})` : "")).join(", ")}</span><b>${money(v.cart_total)}</b><small>${when(v.cart_updated || v.last_seen)} · vino de ${esc(v.source)}</small></div>`).join("")}</div>` : `<p class="muted">Ninguno. Todas las que armaron carrito mandaron el pedido.</p>`;
    $$("#abandonedMini [data-sid]").forEach(r => r.onclick = () => openTimeline(r.dataset.sid));

    $("#lowStock").innerHTML = s.low_stock.length ? s.low_stock.slice(0, 12).map(l => `<li><span>${esc(l.name)} <em>· talle ${esc(l.size)}</em></span><b class="${l.stock ? "" : "zero"}">${l.stock ? "Queda 1" : "Agotado"}</b></li>`).join("") : `<li><em>Todo con stock.</em></li>`;
    $("#perProduct tbody").innerHTML = s.per_product.map(p => `<tr><td>${esc(p.name)}</td><td>${p.vistas}</td><td>${p.carrito}</td><td><b>${p.pedidas}</b></td></tr>`).join("") || `<tr><td colspan="4" class="muted">Sin prendas todavía</td></tr>`;
    $("#demoNote").hidden = !s.has_demo;
  }

  function drawChart(daily) {
    const ch = $("#chart"), ax = $("#chartAxis"); ch.innerHTML = ""; ax.innerHTML = "";
    const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const list = [];
    if (month) { const [y, m] = month.split("-").map(Number), today = new Date(); for (let d = new Date(y, m - 1, 1); d.getMonth() === m - 1 && d <= today; d.setDate(d.getDate() + 1)) list.push(fmt(d)); if (!list.length) list.push(month + "-01"); }
    else for (let i = Math.max(days, 7) - 1; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); list.push(fmt(d)); }
    const map = Object.fromEntries(daily.map(d => [d.day, d])), max = Math.max(1, ...daily.map(d => d.visitas));
    const step = list.length <= 7 ? 1 : list.length <= 31 ? 5 : 15;
    list.forEach((day, i) => {
      const d = map[day] || { visitas: 0, carritos: 0, pedidos: 0 };
      const b = document.createElement("div"); b.className = "bar";
      b.title = `${day.slice(8)}/${day.slice(5, 7)}: ${d.visitas} visitas · ${d.carritos} carritos · ${d.pedidos} pedidos`;
      b.innerHTML = ["l1", "l2", "l3"].map((c, k) => { const v = [d.visitas, d.carritos, d.pedidos][k]; return `<i class="${c}" style="height:${v / max * 100}%;${v ? "min-height:3px" : ""}"></i>`; }).join("");
      ch.appendChild(b);
      const l = document.createElement("span"); l.textContent = i % step === 0 || i === list.length - 1 ? `${+day.slice(8)}/${+day.slice(5, 7)}` : ""; ax.appendChild(l);
    });
  }

  // ------------------------------------------------ recorrido de una visita (desde los carritos del resumen)
  async function openTimeline(sid) {
    const t = await api(`/api/admin/visitors/${encodeURIComponent(sid)}`);
    const v = t.visitor;
    $("#tlBody").innerHTML = `<div class="tl-top"><span class="src ${esc(v.source)}">${esc(v.source)}</span><span>${esc(v.device)}</span><span class="muted">· primera vez ${when(v.first_seen)}${v.visits > 1 ? ` · entró ${v.visits} veces` : ""}</span></div>
      ${t.orders.map(o => `<p><b>Pedido ${esc(o.code)}</b> · ${esc(o.customer_name)} · ${money(o.total)} · ${esc(o.status)}${o.customer_phone ? ` · <a href="https://wa.me/${esc(o.customer_phone.replace(/\D/g, ""))}" target="_blank" rel="noopener">escribirle</a>` : ""}</p>`).join("")}
      <ol>${t.events.filter(e => e.type !== "page" || e.detail !== "Inicio").map(e => `<li class="${esc(e.type)}">${esc(e.label)} ${e.detail ? `<b>${esc(e.detail)}</b>` : ""}<small>${when(e.at)}</small></li>`).join("")}</ol>`;
    openModal("#timeline");
  }

  // ------------------------------------------------ pedidos
  $$("#statusSeg button").forEach(b => b.onclick = () => { statusFilter = b.dataset.s; $$("#statusSeg button").forEach(x => x.classList.toggle("on", x === b)); loadOrders(); });
  async function loadOrders() {
    const orders = await api(`/api/admin/orders${statusFilter ? "?status=" + statusFilter : ""}`);
    if (!statusFilter) setPending(orders.filter(o => o.status === "pendiente").length);
    const list = $("#olist");
    if (!orders.length) { list.innerHTML = `<div class="empty">No hay pedidos ${statusFilter ? "en este estado" : "todavía"}.</div>`; return; }
    list.innerHTML = orders.map(o => {
      const phone = (o.customer_phone || "").replace(/\D/g, ""), wa = phone ? (phone.startsWith("54") ? phone : "549" + phone.replace(/^0/, "")) : "";
      return `<div class="orow" data-id="${o.id}">
        <div><div class="code">${esc(o.code)}</div><div class="date">${when(o.created_at)}</div>${o.source ? `<span class="src ${esc(o.source)}">${esc(o.source)}</span>` : ""}</div>
        <div class="who"><b>${esc(o.customer_name || "Sin nombre")}</b>${wa ? ` · <a class="wa" href="https://wa.me/${wa}" target="_blank" rel="noopener">${esc(o.customer_phone)}</a>` : ""}
          <small>${o.delivery === "envio" ? `Envío: ${esc(o.address)}, ${esc(o.city)}` : "Retira / coordina"}</small>${o.note ? `<small>“${esc(o.note)}”</small>` : ""}
          <div class="items">${o.items.map(i => `<div>${i.qty} × ${esc(i.product_name)}${i.size ? " · talle " + esc(i.size) : ""}${i.color ? " · " + esc(i.color) : ""} — ${money(i.unit_price * i.qty)}</div>`).join("")}</div></div>
        <div class="total">${money(o.total)}<small>${esc(o.payment)}</small></div>
        <select class="${esc(o.status)}" aria-label="Estado">${["pendiente", "confirmado", "entregado", "cancelado"].map(s => `<option value="${s}" ${s === o.status ? "selected" : ""}>${s[0].toUpperCase() + s.slice(1)}</option>`).join("")}</select>
        <div class="onote"><input placeholder="Nota tuya (seña, envío, etc.)" value="${esc(o.admin_note)}"><button type="button" class="btn btn-ghost">Guardar</button></div>
      </div>`;
    }).join("");
    $$(".orow").forEach(r => {
      const id = +r.dataset.id, sel = $("select", r);
      sel.onchange = async () => {
        try { await api(`/api/admin/orders/${id}/status`, { method: "PUT", body: JSON.stringify({ status: sel.value }) }); sel.className = sel.value;
          toast({ confirmado: "Confirmado: se descontó el stock", entregado: "Marcado como entregado", cancelado: "Cancelado: el stock volvió", pendiente: "Volvió a pendiente" }[sel.value]); if (statusFilter) loadOrders(); }
        catch (ex) { toast(ex.message); loadOrders(); }
      };
      $(".onote button", r).onclick = async () => { await api(`/api/admin/orders/${id}`, { method: "PUT", body: JSON.stringify({ admin_note: $(".onote input", r).value }) }); toast("Nota guardada"); };
    });
  }

  // ------------------------------------------------ productos
  async function loadProducts() {
    [products, cats] = await Promise.all([api("/api/admin/products"), api("/api/admin/categories")]);
    const sel = $("#pCat"), cur = sel.value;
    sel.innerHTML = `<option value="">Todas las categorías</option>` + cats.map(c => `<option>${esc(c.name)}</option>`).join("");
    sel.value = cur;
    renderProducts();
  }
  $("#pSearch").oninput = renderProducts; $("#pCat").onchange = renderProducts;
  function renderProducts() {
    const q = $("#pSearch").value.trim().toLowerCase(), c = $("#pCat").value;
    const list = products.filter(p => (!c || p.category === c) && (!q || p.name.toLowerCase().includes(q)));
    $("#plist").innerHTML = list.length ? list.map(p => `<div class="prow" data-id="${p.id}">
      ${p.images[0] ? `<img src="${p.images[0].thumb_url}" alt="" loading="lazy">` : `<div class="noimg"></div>`}
      <div><h4>${esc(p.name)}</h4><p>${esc(p.category || "Sin categoría")} · ${money(p.price)}${p.compare_price > p.price ? ` <s>${money(p.compare_price)}</s>` : ""}${p.card_price_final !== p.price ? ` · tarjeta ${money(p.card_price_final)}` : ""} · ${plural(p.images.length, "foto", "fotos")}</p></div>
      <span class="stock ${p.sold_out ? "zero" : ""}">${p.sizes.length ? (p.sold_out ? "Sin stock" : p.sizes.map(s => `${esc(s.size)}: ${s.stock}`).join(" · ")) : "Sin control de stock"}</span>
      <span class="badges">${p.featured ? '<span class="badge star">Destacada</span>' : ""}<span class="badge ${p.active ? "on" : ""}">${p.active ? "Visible" : "Oculta"}</span></span></div>`).join("")
      : `<div class="empty">${products.length ? "Ninguna prenda coincide." : "Todavía no hay prendas. Creá la primera con + Nueva prenda."}</div>`;
    $$(".prow").forEach(r => r.onclick = () => openEditor(products.find(p => p.id === +r.dataset.id)));
  }
  $("#newProduct").onclick = () => openEditor(null);

  function row(cls, html) { const d = document.createElement("div"); d.className = cls; d.innerHTML = html; $("button.rm", d).onclick = () => d.remove(); return d; }
  const sizeRow = (size = "", stock = 1) => row("srow", `<input placeholder="Talle (S, M, 38, Único…)" value="${esc(size)}" maxlength="20"><input type="number" min="0" value="${stock}" aria-label="Stock" inputmode="numeric"><button type="button" class="rm" aria-label="Quitar">×</button>`);
  const colorRow = (name = "", hex = "#d9c9b6") => row("srow crow", `<input placeholder="Nombre del color" value="${esc(name)}" maxlength="40"><input type="color" value="${esc(hex)}" aria-label="Tono"><button type="button" class="rm" aria-label="Quitar">×</button>`);
  $("#addSize").onclick = () => $("#sizeRows").appendChild(sizeRow());
  $("#addColor").onclick = () => $("#colorRows").appendChild(colorRow());

  function openModal(sel) { $(sel).hidden = false; $("#backdrop").hidden = false; document.body.classList.add("modal-open"); }
  function closeModals() {
    const wasEditor = !$("#editor").hidden;
    $$(".modal").forEach(m => m.hidden = true); $("#backdrop").hidden = true; document.body.classList.remove("modal-open");
    if (wasEditor) { dropPending(); editing = null; loadProducts(); }
  }
  $$("[data-close-modal]").forEach(b => b.onclick = closeModals); $("#backdrop").onclick = closeModals;
  addEventListener("keydown", e => { if (e.key === "Escape") closeModals(); });

  function openEditor(p) {
    editing = p; dropPending();
    const f = $("#editorForm");
    $("#editorTitle").textContent = p ? p.name : "Nueva prenda";
    f.name.value = p ? p.name : "";
    const names = cats.map(c => c.name); if (p && p.category && !names.includes(p.category)) names.push(p.category);
    f.category.innerHTML = `<option value="">Sin categoría</option>` + names.map(n => `<option ${p && n === p.category ? "selected" : ""}>${esc(n)}</option>`).join("");
    if (!p && cats[0]) f.category.value = cats[0].name;
    f.price.value = p ? p.price : ""; f.compare_price.value = p && p.compare_price ? p.compare_price : ""; f.transfer_price.value = p && p.transfer_price ? p.transfer_price : ""; f.card_price.value = p && p.card_price ? p.card_price : "";
    f.card_price.placeholder = +settings.card_surcharge_pct ? `auto (+${settings.card_surcharge_pct}%)` : "auto (= precio)";
    f.transfer_price.placeholder = settings.transfer_discount_pct ? `auto (-${settings.transfer_discount_pct}%)` : "auto";
    f.description.value = p ? p.description : ""; f.active.checked = p ? !!p.active : true; f.featured.checked = p ? !!p.featured : false;
    $("#sizeRows").innerHTML = ""; (p ? p.sizes : [{ size: "S", stock: 1 }, { size: "M", stock: 1 }, { size: "L", stock: 1 }]).forEach(s => $("#sizeRows").appendChild(sizeRow(s.size, s.stock)));
    $("#colorRows").innerHTML = ""; (p ? p.colors : []).forEach(c => $("#colorRows").appendChild(colorRow(c.name, c.hex)));
    $("#deleteProduct").hidden = $("#dupProduct").hidden = !p; $("#editorErr").hidden = true; $("#uploadStatus").hidden = true;
    renderThumbs(); openModal("#editor");
  }
  function collect() {
    const f = $("#editorForm");
    return { name: f.name.value.trim(), category: f.category.value, price: +f.price.value || 0, compare_price: f.compare_price.value ? +f.compare_price.value : null,
      transfer_price: f.transfer_price.value ? +f.transfer_price.value : null, card_price: f.card_price.value ? +f.card_price.value : null, description: f.description.value, active: f.active.checked, featured: f.featured.checked,
      sizes: $$("#sizeRows .srow").map(r => ({ size: r.children[0].value.trim(), stock: Math.max(0, +r.children[1].value || 0) })).filter(s => s.size),
      colors: $$("#colorRows .crow").map(r => ({ name: r.children[0].value.trim(), hex: r.children[1].value })).filter(c => c.name) };
  }
  $("#editorForm").onsubmit = async (e) => {
    e.preventDefault(); $("#editorErr").hidden = true; const btn = $("#saveProduct"); btn.disabled = true;
    try {
      const body = JSON.stringify(collect()), isNew = !editing;
      editing = isNew ? await api("/api/admin/products", { method: "POST", body }) : await api(`/api/admin/products/${editing.id}`, { method: "PUT", body });
      const n = await uploadPending();
      toast(isNew ? `Prenda creada${n ? ` con ${plural(n, "foto", "fotos")}` : ""}` : "Cambios guardados");
      closeModals();
    } catch (ex) { $("#editorErr").textContent = ex.message; $("#editorErr").hidden = false; }
    btn.disabled = false;
  };
  $("#deleteProduct").onclick = async () => {
    if (!editing || !confirm(`¿Eliminar “${editing.name}” con todas sus fotos? No se puede deshacer.\n\nSi solo querés que no se vea, destildá “Visible en la tienda”.`)) return;
    await api(`/api/admin/products/${editing.id}`, { method: "DELETE" }); toast("Prenda eliminada"); closeModals();
  };
  $("#dupProduct").onclick = async () => {
    const copy = await api(`/api/admin/products/${editing.id}/duplicate`, { method: "POST" });
    toast("Copia creada (oculta hasta que le cargues fotos)"); closeModals(); await loadProducts(); openEditor(products.find(p => p.id === copy.id));
  };

  // fotos
  const imgMode = () => ($$('input[name="imgmode"]').find(r => r.checked) || {}).value || "cover";
  function dropPending() { pending.forEach(f => URL.revokeObjectURL(f.preview)); pending = []; }
  async function uploadPending() {
    if (!editing || !pending.length) return 0;
    const fd = new FormData(); pending.forEach(f => fd.append("files", f.file)); fd.append("mode", pending[0].mode);
    $("#uploadStatus").hidden = false; $("#uploadStatus").textContent = `Subiendo ${plural(pending.length, "foto", "fotos")}…`;
    const out = await api(`/api/admin/products/${editing.id}/images`, { method: "POST", body: fd });
    dropPending(); return out.length;
  }
  function renderThumbs() {
    const wrap = $("#thumbs"); wrap.innerHTML = "";
    const list = editing ? editing.images : pending;
    list.forEach((im, i) => {
      const d = document.createElement("div"); d.className = "th" + (i === 0 ? " is-main" : "");
      d.innerHTML = `<img src="${editing ? im.thumb_url + "?v=" + Date.now() : im.preview}" alt="">
        ${i === 0 ? '<span class="first">Principal</span>' : '<button type="button" class="mk">Hacer principal</button>'}
        ${editing ? "" : '<span class="pend">se sube al guardar</span>'}
        <div class="tb"><button type="button" data-mv="-1" aria-label="Antes">←</button><button type="button" class="del">borrar</button><button type="button" data-mv="1" aria-label="Después">→</button></div>`;
      const move = async (j) => {
        if (j < 0 || j >= list.length) return;
        const [x] = list.splice(i, 1); list.splice(j, 0, x);
        if (editing) await api(`/api/admin/products/${editing.id}/images/reorder`, { method: "PUT", body: JSON.stringify({ ids: list.map(y => y.id) }) });
        renderThumbs();
      };
      $$("[data-mv]", d).forEach(b => b.onclick = () => move(i + +b.dataset.mv));
      const mk = $(".mk", d); if (mk) mk.onclick = () => move(0);
      $(".del", d).onclick = async () => {
        if (editing) { if (!confirm("¿Borrar esta foto?")) return; await api(`/api/admin/images/${im.id}`, { method: "DELETE" }); }
        else URL.revokeObjectURL(im.preview);
        list.splice(i, 1); renderThumbs();
      };
      wrap.appendChild(d);
    });
  }
  async function addFiles(files) {
    files = [...(files || [])].filter(f => !f.type || f.type.startsWith("image/") || /\.hei[cf]$/i.test(f.name));
    if (!files.length) return;
    const st = $("#uploadStatus"); st.hidden = false;
    if (!editing) { files.forEach(f => pending.push({ file: f, preview: URL.createObjectURL(f), mode: imgMode() })); st.textContent = `${plural(pending.length, "foto lista", "fotos listas")}: se suben al guardar.`; renderThumbs(); return; }
    st.textContent = `Subiendo ${plural(files.length, "foto", "fotos")}…`;
    const fd = new FormData(); files.forEach(f => fd.append("files", f)); fd.append("mode", imgMode());
    try { const out = await api(`/api/admin/products/${editing.id}/images`, { method: "POST", body: fd }); editing.images.push(...out); renderThumbs(); st.textContent = "Listo"; }
    catch (ex) { st.textContent = ex.message; }
  }
  $("#pickFiles").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = (e) => { addFiles(e.target.files); e.target.value = ""; };
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => addFiles(e.dataTransfer.files));

  // ------------------------------------------------ portada
  async function loadHome() {
    const [sl, st, cs] = await Promise.all([api("/api/admin/slides"), api("/api/admin/settings"), api("/api/admin/categories")]);
    settings = st; cats = cs;
    $("#links").innerHTML = `<option value="/productos">Todos los productos</option>` + cats.map(c => `<option value="/c/${esc(c.slug)}">${esc(c.name)}</option>`).join("");
    renderSlides("hero", sl.hero); renderSlides("banner", sl.banner);
    const f = $("#homeTexts");
    ["banner_text", "section_featured_title", "section_new_title", "related_title", "match_title", "newsletter_title"].forEach(k => f[k].value = st[k] || "");
    f.newsletter_popup.checked = st.newsletter_popup === "1";
  }
  function renderSlides(kind, list) {
    const wrap = $(kind === "hero" ? "#heroList" : "#bannerList");
    wrap.innerHTML = list.length ? "" : `<p class="muted">Todavía no hay ${kind === "hero" ? "fotos" : "cuadros"}.</p>`;
    list.forEach((s, i) => {
      const d = document.createElement("div"); d.className = "slide-ed";
      d.innerHTML = `<img src="${s.url}" alt="">
        <form class="f">
          <label>Título<input name="title" value="${esc(s.title)}" maxlength="80"></label>
          ${kind === "hero" ? `<label>Bajada<input name="subtitle" value="${esc(s.subtitle)}" maxlength="120"></label>` : ""}
          <div class="row2"><label>Texto del botón<input name="button" value="${esc(s.button)}" maxlength="40"></label>
          <label>Lleva a<input name="link" value="${esc(s.link)}" list="links" placeholder="/productos"></label></div>
          <label class="chk"><input type="checkbox" name="active" ${s.active ? "checked" : ""}> Se muestra</label>
          <div class="acts"><button class="btn btn-main">Guardar</button><span class="spacer"></span>
            <button type="button" class="mini-btn" data-mv="-1" aria-label="Antes">←</button><button type="button" class="mini-btn" data-mv="1" aria-label="Después">→</button>
            <button type="button" class="link danger" data-del>Borrar</button></div>
        </form>`;
      const f = $("form", d);
      f.onsubmit = async (e) => { e.preventDefault(); try { await api(`/api/admin/slides/${s.id}`, { method: "PUT", body: JSON.stringify({ title: f.title.value, subtitle: f.subtitle ? f.subtitle.value : "", button: f.button.value, link: f.link.value, active: f.active.checked }) }); toast("Guardado"); } catch (ex) { toast(ex.message); } };
      $$("[data-mv]", d).forEach(b => b.onclick = async () => { const j = i + +b.dataset.mv; if (j < 0 || j >= list.length) return; const [x] = list.splice(i, 1); list.splice(j, 0, x); await api(`/api/admin/slides/${kind}/reorder`, { method: "PUT", body: JSON.stringify({ ids: list.map(y => y.id) }) }); renderSlides(kind, list); });
      $("[data-del]", d).onclick = async () => { if (!confirm("¿Borrar esta foto de la portada?")) return; await api(`/api/admin/slides/${s.id}`, { method: "DELETE" }); list.splice(i, 1); renderSlides(kind, list); };
      wrap.appendChild(d);
    });
  }
  async function addSlide(kind, file) {
    if (!file) return;
    toast("Subiendo foto…");
    const fd = new FormData(); fd.append("kind", kind); fd.append("file", file);
    try { renderSlides(kind, await api("/api/admin/slides", { method: "POST", body: fd })); toast("Foto agregada: completá los textos y guardá"); } catch (ex) { toast(ex.message); }
  }
  $("#addHero").onclick = () => $("#heroFile").click(); $("#heroFile").onchange = (e) => { addSlide("hero", e.target.files[0]); e.target.value = ""; };
  $("#addBanner").onclick = () => $("#bannerFile").click(); $("#bannerFile").onchange = (e) => { addSlide("banner", e.target.files[0]); e.target.value = ""; };
  async function saveSettings(obj, msg = "Guardado") { try { await api("/api/admin/settings", { method: "PUT", body: JSON.stringify(obj) }); Object.assign(settings, obj); toast(msg); } catch (ex) { toast(ex.message); } }
  $("#homeTexts").onsubmit = (e) => { e.preventDefault(); const f = e.target; const o = {}; [...f.elements].forEach(el => { if (el.name) o[el.name] = el.type === "checkbox" ? (el.checked ? "1" : "0") : el.value; }); saveSettings(o, "Textos guardados"); };

  // ------------------------------------------------ ajustes
  const COLORS = [["color_bg", "Fondo", "#f9f7ef"], ["color_text", "Letras", "#9b9d3a"], ["color_bar", "Barra de arriba", "#890e0e"], ["color_button", "Botones", "#705447"], ["color_soft", "Texto sobre botones", "#f5f3c4"]];
  async function loadSettings() {
    settings = await api("/api/admin/settings");
    const fill = (f) => [...f.elements].forEach(el => { if (el.name && settings[el.name] !== undefined) el.value = settings[el.name]; });
    fill($("#brandForm")); fill($("#salesForm"));
    $("#colors").innerHTML = COLORS.map(([k, l]) => `<label class="color"><input type="color" name="${k}" value="${esc(settings[k])}"><span>${l}<small class="muted">${esc(settings[k])}</small></span></label>`).join("");
    $$("#colors input").forEach(i => i.oninput = () => (i.nextElementSibling.querySelector("small").textContent = i.value));
    renderLogo();
    cats = await api("/api/admin/categories"); renderCats();
    const subs = await api("/api/admin/subscribers"); $("#subsCount").textContent = subs.length ? `${plural(subs.length, "persona se anotó", "personas se anotaron")}.` : "Todavía no se anotó nadie.";
  }
  function renderLogo() {
    const ic = document.querySelector('link[rel="icon"]'); if (ic) ic.href = "/favicon?t=" + Date.now(); $("#logoPrev").innerHTML = settings.logo_url ? `<img src="${settings.logo_url}" alt="Logo">` : "Sin logo: se ve el nombre escrito"; $("#rmLogo").hidden = !settings.logo_url; }
  $("#pickLogo").onclick = () => $("#logoFile").click();
  $("#logoFile").onchange = async (e) => { const f = e.target.files[0]; e.target.value = ""; if (!f) return; const fd = new FormData(); fd.append("file", f); try { const r = await api("/api/admin/logo", { method: "POST", body: fd }); settings.logo_url = r.logo_url; renderLogo(); toast("Logo actualizado"); } catch (ex) { toast(ex.message); } };
  $("#rmLogo").onclick = async () => { await api("/api/admin/logo", { method: "DELETE" }); settings.logo_url = ""; renderLogo(); toast("Logo quitado"); };
  $("#resetColors").onclick = () => { COLORS.forEach(([k, , v]) => { const i = $(`#colors [name=${k}]`); i.value = v; i.oninput(); }); toast("Colores originales puestos: tocá Guardar"); };
  const formObj = (f) => Object.fromEntries([...f.elements].filter(el => el.name).map(el => [el.name, el.value]));
  $("#brandForm").onsubmit = (e) => { e.preventDefault(); saveSettings(formObj(e.target)); };
  $("#salesForm").onsubmit = (e) => { e.preventDefault(); saveSettings(formObj(e.target)); };

  function catRow(c = { name: "", products: 0 }) {
    const d = document.createElement("div"); d.className = "srow catrow"; d.dataset.id = c.id ?? "";
    d.innerHTML = `<input value="${esc(c.name)}" maxlength="60" placeholder="Nombre"><span class="cat-count">${c.products ? plural(c.products, "prenda", "prendas") : "vacía"}</span>
      <button type="button" data-mv="-1" aria-label="Subir">↑</button><button type="button" data-mv="1" aria-label="Bajar">↓</button><button type="button" class="rm" aria-label="Quitar">×</button>`;
    $(".rm", d).onclick = () => { if (c.products) return toast(`«${c.name}» tiene prendas: movelas antes de borrarla.`); d.remove(); };
    $$("[data-mv]", d).forEach(b => b.onclick = () => { const sib = +b.dataset.mv < 0 ? d.previousElementSibling : d.nextElementSibling; if (sib) +b.dataset.mv < 0 ? d.parentNode.insertBefore(d, sib) : d.parentNode.insertBefore(sib, d); });
    return d;
  }
  function renderCats() { const w = $("#catRows"); w.innerHTML = ""; cats.forEach(c => w.appendChild(catRow(c))); }
  $("#addCat").onclick = () => { $("#catRows").appendChild(catRow()); $("#catRows").lastElementChild.querySelector("input").focus(); };
  $("#catsForm").onsubmit = async (e) => {
    e.preventDefault(); $("#catsErr").hidden = true;
    const body = $$("#catRows .catrow").map(r => ({ ...(r.dataset.id ? { id: +r.dataset.id } : {}), name: r.children[0].value.trim() })).filter(c => c.name);
    try { await api("/api/admin/categories", { method: "PUT", body: JSON.stringify({ categories: body }) }); cats = await api("/api/admin/categories"); renderCats(); toast("Categorías guardadas"); }
    catch (ex) { $("#catsErr").textContent = ex.message; $("#catsErr").hidden = false; }
  };
  $("#resetMetrics").onclick = async () => {
    if (!confirm("¿Borrar visitas, recorridos y carritos sin pedido?\n\nLos pedidos reales, el stock y las prendas no se tocan. No se puede deshacer.")) return;
    const r = await api("/api/admin/reset-metrics", { method: "POST" }); toast(`Listo: se borraron ${r.deleted} registros`);
  };
  $("#pinForm").onsubmit = async (e) => {
    e.preventDefault(); const f = e.target; $("#pinErr").hidden = true;
    try { await api("/api/admin/pin", { method: "POST", body: JSON.stringify({ current_pin: f.current_pin.value, new_pin: f.new_pin.value }) }); f.reset(); toast("PIN cambiado"); }
    catch (ex) { $("#pinErr").textContent = ex.message; $("#pinErr").hidden = false; }
  };

  // ------------------------------------------------ arranque
  async function start() {
    let me; try { me = await api("/api/admin/me"); } catch { showLogin(); return; }
    if (me.must_change_pin) return showGate();
    $("#login").hidden = $("#pinGate").hidden = true; $("#app").hidden = false;
    settings = await api("/api/admin/settings").catch(() => ({}));
    if (settings.brand_name) { $("#sideBrand").innerHTML = `${esc(settings.brand_name)}<small>PANEL</small>`; document.title = `Panel · ${settings.brand_name}`; }
    showTab("resumen");
  }
  start();
})();
