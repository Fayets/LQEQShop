/* Tienda: portada, listados, ficha, búsqueda, carrito y pedido por WhatsApp.
   Todo el catálogo llega en una sola llamada (/api/store) y la navegación entre páginas
   es del lado del navegador (history.pushState), así se siente rápida en el celular. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => "$" + Number(v || 0).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const store = { settings: {}, categories: [], hero: [], banners: [], products: [] };
  const byId = (id) => store.products.find(p => p.id === id);
  const bySlug = (s) => store.products.find(p => p.slug === s);
  const safe = (fn) => { try { return fn(); } catch { return null; } };
  const toast = (m) => { const t = $("#toast"); t.textContent = m; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2600); };

  // ------------------------------------------------ métricas
  // Un id al azar por navegador. No identifica a la persona: sirve para unir "entró",
  // "miró esta prenda" y "armó este carrito" en una misma fila del panel.
  const SID = safe(() => localStorage.getItem("lqeq_sid")) || (() => {
    const id = (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36)).replace(/[^A-Za-z0-9]/g, "").slice(0, 32);
    safe(() => localStorage.setItem("lqeq_sid", id));
    return id;
  })();
  function track(type, extra = {}) {
    const body = JSON.stringify({ type, session_id: SID, ...extra });
    fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  }
  function trackVisit() {
    if (safe(() => sessionStorage.getItem("lqeq_visit"))) return;
    safe(() => sessionStorage.setItem("lqeq_visit", "1"));
    const q = new URLSearchParams(location.search);
    let ref = document.referrer || "";
    safe(() => { if (new URL(ref).host === location.host) ref = ""; });
    track("visit", { meta: { referrer: ref, utm_source: q.get("utm_source") || "", utm_campaign: q.get("utm_campaign") || "", path: location.pathname } });
  }

  // ------------------------------------------------ carrito (en el navegador + copia en el servidor)
  let cart = safe(() => JSON.parse(localStorage.getItem("lqeq_cart") || "[]")) || [];
  const saveCart = () => {
    safe(() => localStorage.setItem("lqeq_cart", JSON.stringify(cart)));
    $("#cartCount").textContent = cart.reduce((n, i) => n + i.qty, 0);
    clearTimeout(saveCart.t);
    saveCart.t = setTimeout(() => fetch("/api/cart", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: SID, items: cart }) }).catch(() => {}), 700);
  };
  const pct = () => +store.settings.transfer_discount_pct || 0;
  const lineOk = (it) => { const p = byId(it.product_id); return p && (!p.sizes.length || p.sizes.some(s => s.size === it.size)); };

  // ------------------------------------------------ piezas
  const I = {
    card: '<svg viewBox="0 0 24 24"><rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 10h19"/></svg>',
    truck: '<svg viewBox="0 0 24 24"><path d="M2 6h12v10H2zM14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/></svg>',
    store: '<svg viewBox="0 0 24 24"><path d="M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6"/></svg>',
    ig: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/></svg>',
    fb: '<svg viewBox="0 0 24 24"><path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z"/></svg>',
    tt: '<svg viewBox="0 0 24 24"><path d="M14 3v11.5a3.5 3.5 0 1 1-3.5-3.5M14 3c.5 2.6 2.4 4.5 5 5"/></svg>',
    left: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
    right: '<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg>',
  };

  function cardHTML(p) {
    const [a, b] = p.images;
    return `<a class="card" href="/p/${esc(p.slug)}" data-link>
      <div class="card-img">
        ${p.sold_out ? '<span class="tag out">Sin stock</span>' : p.off_pct ? `<span class="tag off">${p.off_pct}% OFF</span>` : ""}
        ${a ? `<img src="${a.thumb_url}" alt="${esc(p.name)}" loading="lazy">` : ""}
        ${b ? `<img class="alt" src="${b.thumb_url}" alt="" loading="lazy">` : ""}
      </div>
      <div class="card-info">
        <p class="card-name">${esc(p.name)}</p>
        <p class="card-price">${p.off_pct ? `<s>${money(p.compare_price)}</s>` : ""}${money(p.price)}</p>
        ${pct() || p.transfer_price ? `<p class="card-transfer">${money(p.transfer_price_final)} con Transferencia</p>` : ""}
      </div></a>`;
  }

  function carouselHTML(title, list) {
    if (!list.length) return "";
    return `<section class="section"><h2 class="section-title">${esc(title)}</h2>
      <div class="carousel"><button class="c-arrow prev" aria-label="Anterior">${I.left}</button>
      <div class="track">${list.map(cardHTML).join("")}</div>
      <button class="c-arrow next" aria-label="Siguiente">${I.right}</button></div></section>`;
  }
  function wireCarousels(root) {
    $$(".carousel", root).forEach(c => {
      const t = $(".track", c), prev = $(".prev", c), next = $(".next", c);
      const upd = () => { prev.disabled = t.scrollLeft < 4; next.disabled = t.scrollLeft + t.clientWidth >= t.scrollWidth - 4; };
      prev.onclick = () => t.scrollBy({ left: -t.clientWidth, behavior: "smooth" });
      next.onclick = () => t.scrollBy({ left: t.clientWidth, behavior: "smooth" });
      t.addEventListener("scroll", upd, { passive: true }); upd();
    });
  }

  // ------------------------------------------------ vistas
  let heroTimer;
  function viewHome() {
    const s = store.settings;
    const featured = store.products.filter(p => p.featured);
    const newest = [...store.products].sort((a, b) => b.created_at.localeCompare(a.created_at) || a.sort_order - b.sort_order).slice(0, 12);
    const hero = store.hero.length ? `<section class="hero" id="hero">
      ${store.hero.map((h, i) => `<div class="slide${i ? "" : " on"}">
        <picture><source media="(max-width:700px)" srcset="${h.mobile_url}"><img src="${h.url}" alt="" ${i ? 'loading="lazy"' : 'fetchpriority="high"'}></picture>
        ${h.title || h.subtitle || h.button ? `<div class="slide-copy">${h.title ? `<h2>${esc(h.title)}</h2>` : ""}${h.subtitle ? `<p>${esc(h.subtitle)}</p>` : ""}${h.button ? `<a class="btn-shop" href="${esc(h.link || "/productos")}" ${(h.link || "/").startsWith("/") ? "data-link" : 'target="_blank" rel="noopener"'}>${esc(h.button)}</a>` : ""}</div>` : ""}
      </div>`).join("")}
      ${store.hero.length > 1 ? `<button class="hero-arrow prev" aria-label="Anterior">${I.left}</button><button class="hero-arrow next" aria-label="Siguiente">${I.right}</button><div class="dots">${store.hero.map((_, i) => `<button data-i="${i}" class="${i ? "" : "on"}" aria-label="Foto ${i + 1}"></button>`).join("")}</div>` : ""}
    </section>` : "";
    const banners = store.banners.length ? `<div class="banners">${store.banners.map(b => `<a class="banner" href="${esc(b.link || "/productos")}" data-link><img src="${b.url}" alt="${esc(b.title)}" loading="lazy"><div><h3>${esc(b.title)}</h3>${b.button ? `<span>${esc(b.button)}</span>` : ""}</div></a>`).join("")}</div>` : "";
    $("#view").innerHTML = hero + carouselHTML(s.section_featured_title || "DESTACADOS", featured.length ? featured : newest) + banners +
      carouselHTML(s.section_new_title || "NEW IN", newest);
    wireCarousels($("#view"));
    wireHero();
    document.title = `${s.brand_name} ${s.brand_tagline || ""}`.trim();
  }
  function wireHero() {
    clearInterval(heroTimer);
    const h = $("#hero"); if (!h) return;
    const slides = $$(".slide", h), dots = $$(".dots button", h); let i = 0;
    const go = (n) => { i = (n + slides.length) % slides.length; slides.forEach((s, k) => s.classList.toggle("on", k === i)); dots.forEach((d, k) => d.classList.toggle("on", k === i)); };
    const auto = () => { clearInterval(heroTimer); if (slides.length > 1) heroTimer = setInterval(() => go(i + 1), 6000); };
    dots.forEach(d => d.onclick = () => { go(+d.dataset.i); auto(); });
    const p = $(".hero-arrow.prev", h), n = $(".hero-arrow.next", h);
    if (p) p.onclick = () => { go(i - 1); auto(); };
    if (n) n.onclick = () => { go(i + 1); auto(); };
    let x0 = null;
    h.addEventListener("touchstart", e => (x0 = e.touches[0].clientX), { passive: true });
    h.addEventListener("touchend", e => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) { go(i + (dx < 0 ? 1 : -1)); auto(); } x0 = null; });
    auto();
  }

  function viewList(cat) {
    const c = cat ? store.categories.find(x => x.slug === cat) : null;
    let list = c ? store.products.filter(p => p.category === c.name) : store.products;
    const sort = new URLSearchParams(location.search).get("orden") || "";
    const sorted = [...list];
    if (sort === "menor") sorted.sort((a, b) => a.price - b.price);
    else if (sort === "mayor") sorted.sort((a, b) => b.price - a.price);
    else if (sort === "nuevo") sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
    sorted.sort((a, b) => a.sold_out - b.sold_out);   // lo agotado siempre al final
    const title = c ? c.name : "Todos los productos";
    $("#view").innerHTML = `<div class="list-head"><p class="crumbs"><a href="/" data-link>Inicio</a> . ${esc(title)}</p><h1>${esc(title)}</h1></div>
      <div class="list-tools"><div class="chips"><a href="/productos" data-link class="${c ? "" : "on"}">Todo</a>${store.categories.map(x => `<a href="/c/${esc(x.slug)}" data-link class="${c && c.id === x.id ? "on" : ""}">${esc(x.name)}</a>`).join("")}</div>
      <select class="sort" id="sort" aria-label="Ordenar"><option value="">Destacados</option><option value="nuevo">Más nuevos</option><option value="menor">Precio: menor a mayor</option><option value="mayor">Precio: mayor a menor</option></select></div>
      <div class="wrap">${sorted.length ? `<div class="grid">${sorted.map(cardHTML).join("")}</div>` : `<p class="empty">Todavía no hay prendas en esta categoría.</p>`}</div>`;
    $("#sort").value = sort;
    $("#sort").onchange = (e) => { const u = new URL(location.href); e.target.value ? u.searchParams.set("orden", e.target.value) : u.searchParams.delete("orden"); history.replaceState(null, "", u); viewList(cat); };
    document.title = `${title} · ${store.settings.brand_name}`;
  }

  function viewProduct(slug) {
    const p = bySlug(slug);
    if (!p) { $("#view").innerHTML = `<p class="empty">Esta prenda ya no está disponible. <a href="/productos" data-link><u>Ver todos los productos</u></a></p>`; return; }
    track("view_product", { product_id: p.id });
    const s = store.settings, cat = store.categories.find(c => c.name === p.category);
    const n = +s.installments || 0;
    let size = p.sizes.length === 1 && p.sizes[0].stock > 0 ? p.sizes[0].size : null;
    let color = p.colors.length === 1 ? p.colors[0].name : null;
    const acc = [["info_payment", "Medios de pago", I.card], ["info_shipping", "Medios de envío", I.truck], ["info_store", "Nuestro local", I.store]]
      .filter(([k]) => s[k]).map(([k, t, ic]) => `<details><summary>${ic}${t}</summary><p>${esc(s[k])}${k === "info_store" && s.address ? `<br>${esc(s.address)}` : ""}</p></details>`).join("");
    $("#view").innerHTML = `<div class="pdp">
      <div><div class="pdp-media" id="media">${p.images.map((im, i) => `<img src="${im.url}" alt="${esc(p.name)} ${i + 1}" ${i ? 'loading="lazy"' : ""}>`).join("") || '<img alt="">'}</div>
        ${p.images.length > 1 ? `<div class="pdp-dots" id="mdots">${p.images.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div>` : ""}</div>
      <div class="pdp-info">
        <p class="crumbs"><a href="/" data-link>Inicio</a> . ${cat ? `<a href="/c/${esc(cat.slug)}" data-link>${esc(cat.name)}</a> . ` : ""}${esc(p.name)}</p>
        <h1>${esc(p.name)}</h1>
        <div class="price-row"><span class="price-now">${p.off_pct ? `<s>${money(p.compare_price)}</s>` : ""}${money(p.price)}${p.off_pct ? `<span class="price-off">${p.off_pct}% OFF</span>` : ""}</span>
          ${n > 1 ? `<span class="cuotas">${n} cuotas sin interés de ${money(p.price / n)}</span>` : ""}</div>
        ${pct() || p.transfer_price ? `<p class="transfer">${money(p.transfer_price_final)} con Transferencia</p>` : ""}
        ${p.colors.length ? `<div class="opt"><div class="opt-label">Color<b id="colorName">${esc(color || "")}</b></div><div class="opts" id="colors">${p.colors.map(c => `<button class="chip${c.name === color ? " on" : ""}" data-v="${esc(c.name)}"><i style="background:${esc(c.hex)}"></i>${esc(c.name)}</button>`).join("")}</div></div>` : ""}
        ${p.sizes.length ? `<div class="opt"><div class="opt-label">Talle<b id="sizeName">${esc(size || "")}</b></div><div class="opts" id="sizes">${p.sizes.map(z => `<button class="chip${z.size === size ? " on" : ""}" data-v="${esc(z.size)}" ${z.stock > 0 ? "" : "disabled"}>${esc(z.size)}</button>`).join("")}</div></div>` : ""}
        <div class="buy">
          <div class="qty"><button type="button" data-q="-1" aria-label="Menos">−</button><input id="qty" type="number" value="1" min="1" max="20" aria-label="Cantidad"><button type="button" data-q="1" aria-label="Más">+</button></div>
          <button class="btn-main" id="add" ${p.sold_out ? "disabled" : ""}>${p.sold_out ? "Sin stock" : "Agregar al carrito"}</button>
        </div>
        <p class="pdp-err" id="perr"></p>
        ${acc ? `<div class="acc">${acc}</div>` : ""}
        ${p.description ? `<div class="desc">${esc(p.description)}</div>` : ""}
      </div></div>
      ${carouselHTML(s.related_title || "TAMBIÉN TE PUEDE GUSTAR", store.products.filter(x => x.id !== p.id && x.category === p.category && !x.sold_out).slice(0, 12))}
      ${carouselHTML(s.match_title || "PERFECT MATCH", store.products.filter(x => x.category !== p.category && !x.sold_out).slice(0, 12))}`;
    wireCarousels($("#view"));
    const pick = (box, set, label) => box && box.addEventListener("click", e => { const b = e.target.closest(".chip"); if (!b || b.disabled) return; $$(".chip", box).forEach(x => x.classList.toggle("on", x === b)); set(b.dataset.v); $(label).textContent = b.dataset.v; $("#perr").textContent = ""; });
    pick($("#colors"), v => (color = v), "#colorName");
    pick($("#sizes"), v => (size = v), "#sizeName");
    $$(".buy [data-q]").forEach(b => b.onclick = () => { const q = $("#qty"); q.value = Math.min(20, Math.max(1, (+q.value || 1) + +b.dataset.q)); });
    const media = $("#media"), mdots = $$("#mdots i");
    if (mdots.length) media.addEventListener("scroll", () => { const i = Math.round(media.scrollLeft / media.clientWidth); mdots.forEach((d, k) => d.classList.toggle("on", k === i)); }, { passive: true });
    $("#add").onclick = () => {
      if (p.colors.length && !color) return ($("#perr").textContent = "Elegí un color");
      if (p.sizes.length && !size) return ($("#perr").textContent = "Elegí un talle");
      const qty = Math.min(20, Math.max(1, +$("#qty").value || 1));
      const stock = p.sizes.length ? p.sizes.find(z => z.size === size).stock : 99;
      const line = cart.find(i => i.product_id === p.id && i.size === size && i.color === color);
      const want = (line ? line.qty : 0) + qty;
      if (want > stock) return ($("#perr").textContent = `Queda${stock === 1 ? "" : "n"} ${stock} en talle ${size}`);
      line ? (line.qty = want) : cart.push({ product_id: p.id, size, color, qty });
      saveCart();
      track("add_to_cart", { product_id: p.id, size, meta: { color, qty } });
      openCart();
    };
    document.title = `${p.name} · ${s.brand_name}`;
  }

  function viewSearch(q) {
    q = (q || "").trim();
    $("#view").innerHTML = `<div class="list-head"><h1>Resultados para “${esc(q)}”</h1></div><div class="wrap">${searchHTML(q)}</div>`;
  }
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  function searchHTML(q) {
    const t = norm(q); if (!t) return "";
    const hits = store.products.filter(p => norm(`${p.name} ${p.category} ${p.description}`).includes(t));
    return hits.length ? `<div class="grid">${hits.map(cardHTML).join("")}</div>` : `<p class="empty">No encontramos prendas para “${esc(q)}”.</p>`;
  }

  // ------------------------------------------------ router
  function route(push) {
    if (push) history.pushState(null, "", push);
    closeAll();
    const path = location.pathname;
    let m;
    if ((m = path.match(/^\/p\/([^/]+)/))) viewProduct(decodeURIComponent(m[1]));
    else if ((m = path.match(/^\/c\/([^/]+)/))) viewList(decodeURIComponent(m[1]));
    else if (path === "/productos") viewList(null);
    else if (path === "/buscar") viewSearch(new URLSearchParams(location.search).get("q"));
    else viewHome();
    window.scrollTo(0, 0);
    track("page", { meta: { path: path + location.search, title: document.title.split(" · ")[0] } });
  }
  document.addEventListener("click", e => {
    const a = e.target.closest("a[data-link]");
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || a.target === "_blank") return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    e.preventDefault();
    if (url.pathname + url.search !== location.pathname + location.search) route(url.pathname + url.search);
    else closeAll();
  });
  addEventListener("popstate", () => route());

  // ------------------------------------------------ drawers
  const scrim = $("#scrim");
  function openDrawer(el) { closeAll(); el.classList.add("open"); el.setAttribute("aria-hidden", "false"); scrim.hidden = false; document.body.classList.add("lock"); }
  function closeAll() {
    $$(".drawer.open").forEach(d => { d.classList.remove("open"); d.setAttribute("aria-hidden", "true"); });
    $("#search").hidden = true; scrim.hidden = true; document.body.classList.remove("lock");
  }
  scrim.onclick = closeAll;
  $$("[data-close]").forEach(b => b.onclick = closeAll);
  addEventListener("keydown", e => { if (e.key === "Escape") { closeAll(); $("#pop").hidden = true; } });
  $("#openMenu").onclick = () => openDrawer($("#menu"));
  $("#openCart").onclick = () => openCart();
  $("#openSearch").onclick = () => { closeAll(); $("#search").hidden = false; document.body.classList.add("lock"); $("#searchInput").focus(); };
  $("#searchInput").oninput = (e) => { $("#searchResults").innerHTML = searchHTML(e.target.value); };
  $("#searchForm").onsubmit = (e) => { e.preventDefault(); const q = $("#searchInput").value.trim(); if (!q) return; track("search", { meta: { q } }); route("/buscar?q=" + encodeURIComponent(q)); };

  // ------------------------------------------------ carrito
  function openCart() { renderCart(); openDrawer($("#cart")); track("open_cart"); }
  function totals() {
    let list = 0, transfer = 0;
    cart.forEach(i => { const p = byId(i.product_id); if (!p) return; list += p.price * i.qty; transfer += p.transfer_price_final * i.qty; });
    return { list, transfer };
  }
  function renderCart() {
    cart = cart.filter(lineOk);
    const body = $("#cartBody"); $("#cartTitle").textContent = "CARRITO DE COMPRAS";
    if (!cart.length) { body.innerHTML = `<div class="cart-empty"><p>El carrito de compras está vacío.</p><a href="/productos" data-link><u>Ver productos</u></a></div>`; saveCart(); return; }
    const t = totals();
    body.innerHTML = `<div class="cart-items">${cart.map((i, k) => { const p = byId(i.product_id); const im = p.images[0];
      return `<div class="ci">${im ? `<img src="${im.thumb_url}" alt="">` : "<span></span>"}
        <div><h5>${esc(p.name)}</h5>${i.size ? `<small>Talle: ${esc(i.size)}</small>` : ""}${i.color ? `<small>Color: ${esc(i.color)}</small>` : ""}
        <div class="qty"><button data-k="${k}" data-d="-1" aria-label="Menos">−</button><input value="${i.qty}" readonly aria-label="Cantidad"><button data-k="${k}" data-d="1" aria-label="Más">+</button></div></div>
        <div class="ci-right"><span>${money(p.price * i.qty)}</span><button class="ci-del" data-del="${k}">Borrar</button></div></div>`; }).join("")}</div>
      <div class="cart-foot">
        <div class="sum"><span>Subtotal</span><span>${money(t.list)}</span></div>
        ${t.transfer < t.list ? `<div class="sum total"><span>Total con transferencia</span><span>${money(t.transfer)}</span></div>` : `<div class="sum total"><span>Total</span><span>${money(t.list)}</span></div>`}
        <button class="btn-main" id="toCheckout">Iniciar compra</button>
        <button class="link-btn" data-close>Ver más productos</button>
      </div>`;
    $$("[data-d]", body).forEach(b => b.onclick = () => {
      const i = cart[+b.dataset.k], p = byId(i.product_id), max = p.sizes.length ? (p.sizes.find(z => z.size === i.size) || { stock: 0 }).stock : 20;
      const q = i.qty + +b.dataset.d; if (q > max) return toast(`No hay más stock de talle ${i.size}`);
      if (q < 1) { cart.splice(+b.dataset.k, 1); track("remove_from_cart", { product_id: p.id, size: i.size }); } else i.qty = q;
      saveCart(); renderCart();
    });
    $$("[data-del]", body).forEach(b => b.onclick = () => { const i = cart.splice(+b.dataset.del, 1)[0]; track("remove_from_cart", { product_id: i.product_id, size: i.size }); saveCart(); renderCart(); });
    $$("[data-close]", body).forEach(b => b.onclick = closeAll);
    $("#toCheckout").onclick = renderCheckout;
  }

  function renderCheckout() {
    track("begin_checkout");
    const t = totals(), d = pct();
    const saved = safe(() => JSON.parse(localStorage.getItem("lqeq_buyer") || "{}")) || {};
    $("#cartTitle").textContent = "TUS DATOS";
    $("#cartBody").innerHTML = `<form class="checkout" id="co">
      <label>Nombre y apellido<input name="customer_name" required minlength="2" maxlength="80" autocomplete="name" value="${esc(saved.customer_name)}"></label>
      <label>WhatsApp<input name="customer_phone" required minlength="6" maxlength="40" inputmode="tel" autocomplete="tel" placeholder="11 2345 6789" value="${esc(saved.customer_phone)}"></label>
      <label>¿Cómo lo recibís?<div class="radios">
        <label class="radio"><input type="radio" name="delivery" value="retiro" checked>Retiro / coordino por WhatsApp</label>
        <label class="radio"><input type="radio" name="delivery" value="envio">Envío a domicilio</label></div></label>
      <div id="addr" hidden style="display:grid;gap:14px">
        <label>Dirección<input name="address" maxlength="160" autocomplete="street-address" value="${esc(saved.address)}"></label>
        <label>Localidad y provincia<input name="city" maxlength="80" autocomplete="address-level2" value="${esc(saved.city)}"></label>
      </div>
      <label>¿Cómo pagás?<div class="radios">
        <label class="radio"><input type="radio" name="payment" value="transferencia" checked>Transferencia<em>${money(t.transfer)}</em></label>
        <label class="radio"><input type="radio" name="payment" value="efectivo">Efectivo<em>${money(t.transfer)}</em></label>
        <label class="radio"><input type="radio" name="payment" value="tarjeta">Tarjeta${+store.settings.installments > 1 ? ` · ${store.settings.installments} cuotas sin interés` : ""}<em>${money(t.list)}</em></label></div></label>
      <label>¿Algo que quieras aclarar? <textarea name="note" rows="2" maxlength="500"></textarea></label>
      <p class="co-err" id="coErr" hidden></p>
      <button class="btn-main" id="coSend">Enviar pedido por WhatsApp</button>
      <button type="button" class="link-btn" id="coBack">Volver al carrito</button>
      ${d ? `<p style="font-size:11px;margin:0;text-align:center">Pagando con transferencia o efectivo tenés ${d}% de descuento.</p>` : ""}
    </form>`;
    const f = $("#co");
    f.addEventListener("change", () => { $("#addr").hidden = f.delivery.value !== "envio"; });
    $("#coBack").onclick = renderCart;
    f.onsubmit = async (e) => {
      e.preventDefault();
      const err = $("#coErr"); err.hidden = true;
      const data = Object.fromEntries(new FormData(f));
      if (data.delivery === "envio" && (!data.address.trim() || !data.city.trim())) { err.textContent = "Completá la dirección y la localidad."; err.hidden = false; return; }
      // La ventana de WhatsApp se abre ahora, dentro del click: si se abriera después
      // de esperar al servidor, el navegador la bloquearía como pop-up.
      const w = window.open("", "_blank");
      $("#coSend").disabled = true;
      try {
        const r = await fetch("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...data, items: cart, session_id: SID }) });
        const out = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(typeof out.detail === "string" ? out.detail : "Revisá los datos e intentá de nuevo.");
        safe(() => localStorage.setItem("lqeq_buyer", JSON.stringify({ customer_name: data.customer_name, customer_phone: data.customer_phone, address: data.address, city: data.city })));
        cart = []; safe(() => localStorage.setItem("lqeq_cart", "[]")); $("#cartCount").textContent = 0;
        if (w) w.location.href = out.whatsapp_url; else location.href = out.whatsapp_url;
        $("#cartTitle").textContent = "¡GRACIAS!";
        $("#cartBody").innerHTML = `<div class="done"><h3>Pedido ${esc(out.order.code)} enviado</h3><p>Se abrió WhatsApp con el detalle. Mandá el mensaje y te respondemos para coordinar el pago y la entrega.</p>
          <a class="btn-main" style="display:grid;place-items:center;width:100%;text-decoration:none" href="${esc(out.whatsapp_url)}" target="_blank" rel="noopener">Abrir WhatsApp de nuevo</a>
          <button class="link-btn" data-close>Seguir mirando</button></div>`;
        $$("#cartBody [data-close]").forEach(b => b.onclick = closeAll);
      } catch (ex) {
        if (w) w.close();
        err.textContent = ex.message; err.hidden = false; $("#coSend").disabled = false;
      }
    };
  }

  // ------------------------------------------------ marco (header, menú, footer)
  function frame() {
    const s = store.settings;
    $("#logo").innerHTML = s.logo_url ? `<img src="${s.logo_url}" alt="${esc(s.brand_name)}">` : `<b>${esc(s.brand_name)}</b>${s.brand_tagline ? `<small>${esc(s.brand_tagline)}</small>` : ""}`;
    const msgs = (s.banner_text || "").split("|").map(x => x.trim()).filter(Boolean);
    if (msgs.length) {
      const one = msgs.map(m => `<span>${esc(m)}</span>`).join("");
      $("#adbarTrack").innerHTML = one.repeat(Math.max(2, Math.ceil(8 / msgs.length)) * 2);
    } else $("#adbar").hidden = true;
    const wa = s.whatsapp_number ? `https://wa.me/${s.whatsapp_number}` : "";
    const waF = $("#waFloat"); if (wa) { waF.href = wa; waF.onclick = () => track("whatsapp_float"); } else waF.hidden = true;
    const ig = s.instagram ? `https://instagram.com/${s.instagram}` : "";
    if (ig) { $("#igTop").href = ig; $("#igTop").hidden = false; }
    $("#menuList").innerHTML = `<a href="/" data-link>Inicio</a><a href="/productos" data-link>Ver todos los productos</a>` +
      store.categories.map(c => `<a class="sub" href="/c/${esc(c.slug)}" data-link>${esc(c.name)}</a>`).join("") +
      (wa ? `<a href="${wa}" target="_blank" rel="noopener">Contacto</a>` : "");
    $("#newsTitle").textContent = s.newsletter_title || "";
    $("#socials").innerHTML = [[ig, I.ig, "Instagram"], [s.facebook && `https://facebook.com/${s.facebook}`, I.fb, "Facebook"], [s.tiktok && `https://tiktok.com/@${s.tiktok}`, I.tt, "TikTok"]]
      .filter(x => x[0]).map(([u, ic, l]) => `<a href="${esc(u)}" target="_blank" rel="noopener" aria-label="${l}">${ic}</a>`).join("");
    $("#footCats").innerHTML = `<li><a href="/" data-link>Inicio</a></li><li><a href="/productos" data-link>Shop now</a></li>` + store.categories.map(c => `<li><a href="/c/${esc(c.slug)}" data-link>${esc(c.name)}</a></li>`).join("");
    const phone = s.whatsapp_number ? "+" + s.whatsapp_number.replace(/^(\d{2})(\d)(\d{2})(\d{4})(\d+)$/, "$1 $2 $3 $4 $5") : "";
    $("#footContact").innerHTML = [wa && `<li><a href="${wa}" target="_blank" rel="noopener">${esc(phone)}</a></li>`, s.email && `<li><a href="mailto:${esc(s.email)}">${esc(s.email)}</a></li>`, s.address && `<li>${esc(s.address)}</li>`].filter(Boolean).join("");
    $("#copy").textContent = `Copyright ${s.brand_name} ${s.brand_tagline || ""} - ${new Date().getFullYear()}. Todos los derechos reservados.`.replace("  ", " ");
    addEventListener("scroll", () => $("#header").classList.toggle("scrolled", scrollY > 10), { passive: true });
  }

  // newsletter (pie + popup)
  async function subscribe(data) {
    const r = await fetch("/api/newsletter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...data, session_id: SID }) });
    if (!r.ok) { const o = await r.json().catch(() => ({})); throw new Error(typeof o.detail === "string" ? o.detail : "Revisá el email"); }
    safe(() => localStorage.setItem("lqeq_news", "1"));
  }
  $("#newsInline").onsubmit = async (e) => { e.preventDefault(); try { await subscribe(Object.fromEntries(new FormData(e.target))); e.target.hidden = true; $("#newsInlineOk").hidden = false; } catch (ex) { toast(ex.message); } };
  $("#popForm").onsubmit = async (e) => { e.preventDefault(); try { await subscribe(Object.fromEntries(new FormData(e.target))); e.target.hidden = true; $("#popOk").hidden = false; setTimeout(() => ($("#pop").hidden = true), 1800); } catch (ex) { toast(ex.message); } };
  $("#popClose").onclick = () => { $("#pop").hidden = true; };
  $("#pop").onclick = (e) => { if (e.target.id === "pop") $("#pop").hidden = true; };
  function maybePopup() {
    if (store.settings.newsletter_popup !== "1" || safe(() => localStorage.getItem("lqeq_news") || sessionStorage.getItem("lqeq_pop"))) return;
    setTimeout(() => { if (document.body.classList.contains("lock")) return; safe(() => sessionStorage.setItem("lqeq_pop", "1")); $("#pop").hidden = false; }, 14000);
  }
  if (!safe(() => localStorage.getItem("lqeq_cookies"))) { $("#cookies").hidden = false; document.body.classList.add("has-cookies"); }
  $("#cookiesOk").onclick = () => { safe(() => localStorage.setItem("lqeq_cookies", "1")); $("#cookies").hidden = true; document.body.classList.remove("has-cookies"); };

  // ------------------------------------------------ arranque
  (async () => {
    try {
      Object.assign(store, await (await fetch("/api/store")).json());
    } catch { $("#view").innerHTML = `<p class="empty">No pudimos cargar la tienda. Probá recargar la página.</p>`; return; }
    frame();
    saveCart();
    trackVisit();
    route();
    maybePopup();
  })();
})();
