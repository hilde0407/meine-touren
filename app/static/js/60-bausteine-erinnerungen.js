/* =====================  3.32.0 Erinnerungen: einstellbar und in der Größe änderbar  =====================
   Die Kachel „Erinnerungen“ der Übersicht (Abschnitt „erinn“, bisher fest: 6 zufällige Fotos) ist jetzt ein Baustein wie „Dein Jahr“: Schlüssel und gespeicherte Layouts bleiben gültig,
   ohne Konfiguration sieht und verhält sie sich wie bisher (6 zufällige Fotos, Link zur Zufalls-Diashow). Sie lässt sich außerdem als weitere Kachel mit anderen Einstellungen hinzufügen.
   Konfiguration (cfg, geprüft in app/layout.py „_erinn_cfg“; gespeichert werden nur Abweichungen vom Standard):
     mode    random | best | day | recent      Auswahl der Fotos: zufällig, beste Fotos, an diesem Tag in früheren Jahren, neueste
     n       3 | 6 | 9 | 12                    Anzahl             sports, range, yr  Sportart und Zeitraum wie im Filtersystem (53-filter.js)
     view    grid | strip | show               Raster, Streifen (seitlich wischen) oder Einzelbild-Show (blättert selbst)
     ratio   sq | 43 | 169 | orig               Seitenverhältnis der Kacheln (orig = Originalformat, in der Show: ganzes Bild)
     size    s | m | l                          Größe der Bilder (Raster, Streifen)      height  k | n | h   Höhe der Einzelbild-Show      tempo  3 | 5 | 8 | 12  Sekunden je Bild
     caption Bildunterschrift (Tourname und Datum)      shuffle  Knopf „Neu mischen“      link  false = ohne Link „Diashow starten“      title  eigener Titel
   Die Fotos kommen von GET /api/photos (Filter sport, date_from, date_to, day, before, best, app/fotofilter.py). Die Breite wählt man wie bei allen Bausteinen (Raster 49-seitenlayout.js);
   die Spaltenzahl im Raster richtet sich nach der tatsächlichen Breite der Kachel (ResizeObserver), die Höhen nach der Breite der Kachel (Container-Abfragen in style.css „3.32.0“). */
const ER_MODES = [["random", "Zufällige Fotos"], ["best", "Beste Fotos"], ["day", "An diesem Tag in früheren Jahren"], ["recent", "Neueste Fotos"]];
const ER_N = [3, 6, 9, 12];
const ER_VIEWS = [["grid", "Raster"], ["strip", "Streifen"], ["show", "Einzelbild-Show"]];
const ER_RATIOS = [["sq", "Quadratisch"], ["43", "4:3"], ["169", "16:9"], ["orig", "Originalformat"]];
const ER_SIZES = [["s", "Klein"], ["m", "Mittel"], ["l", "Groß"]];
const ER_HEIGHTS = [["k", "Kompakt"], ["n", "Normal"], ["h", "Hoch"]];
const ER_TEMPO = [3, 5, 8, 12];
const ER_MINW = {s: 90, m: 130, l: 170};                                                   // Mindestbreite einer Kachel im Raster (px)
const ER_PX = {s: 400, m: 400, l: 500};                                                     // Größe der geladenen Vorschaubilder je „Größe der Bilder“ (3.54.0: nur vorab erzeugte Größen, 500 statt 600)
const erPick = (v, list, d) => (list.includes(v) ? v : d);
const erIds = l => l.map(x => x[0]);
/* Einstellung mit allen Standardwerten (fehlende oder ungültige Werte → Standard) */
function erCfg(cfg) {
  cfg = cfg || {};
  return {
    mode: erPick(cfg.mode, erIds(ER_MODES), "random"), n: erPick(+cfg.n, ER_N, 6), view: erPick(cfg.view, erIds(ER_VIEWS), "grid"), ratio: erPick(cfg.ratio, erIds(ER_RATIOS), "sq"),
    size: erPick(cfg.size, erIds(ER_SIZES), "m"), height: erPick(cfg.height, erIds(ER_HEIGHTS), "n"), tempo: erPick(+cfg.tempo, ER_TEMPO, 5),
    caption: cfg.caption === true, shuffle: cfg.shuffle === true, link: cfg.link !== false,
  };
}
const erModeName = m => (ER_MODES.find(x => x[0] === m) || ER_MODES[0])[1];
/* Kurztext der Einstellung (Kopf der Kachel, Zeile im Bearbeitungsmodus): Auswahl, Sportart, Zeitraum */
function erKurz(cfg) {
  const m = erCfg(cfg).mode;
  return [...(m === "random" ? [] : [erModeName(m)]), ...flParts(cfg || {}, "all")];
}
const erMd = () => {
  const n = new Date();
  return `${pad2(n.getMonth() + 1)}-${pad2(n.getDate())}`;
};
/* Abfrage der Fotos; ohne Einstellung genau die bisherige (random=true, limit=6) */
function erUrl(cfg, fix) {
  const c = erCfg(cfg), u = new URLSearchParams();
  if (c.mode === "random" || c.mode === "day") u.set("random", "true");
  else if (c.mode === "best") u.set("best", "true");
  else u.set("recent", "1");
  u.set("limit", String(c.n));
  if (c.mode === "day") {
    u.set("day", erMd());
    u.set("before", String(new Date().getFullYear()));
  }
  if (cfg && cfg.sports && cfg.sports.length && sgPlain(cfg.sports).length) u.set("sport", sgPlain(cfg.sports).join(","));      // 3.59.0: Fotos und Diashow kennen keine Statistik-Gruppen: aufgelöst
  if (cfg && cfg.range && cfg.range !== "all") {
    const R = flRange(cfg, "all");
    if (R.from) u.set("date_from", R.from);
    if (R.to) u.set("date_to", R.to);
  }
  if (fix) {                                                                                 // 3.33.0 Reise-Diashow: der Zeitraum der Reise (JJJJ-MM-TT) ersetzt jeden Filter
    u.set("date_from", fix.from);
    u.set("date_to", fix.to);
  }
  return "/api/photos?" + u;
}
/* Link „Diashow starten“: nur Parameter, die slideshow.html versteht (js/seite-slideshow.js): random, best, recent, day, before, sport, from, to, year, sec */
function erSlideUrl(cfg, fix) {
  const c = erCfg(cfg), u = new URLSearchParams();
  if (c.mode === "random") u.set("random", "1");
  else if (c.mode === "best") u.set("best", "60");
  else if (c.mode === "recent") u.set("recent", "1");
  else {
    u.set("day", erMd());
    u.set("before", String(new Date().getFullYear()));
  }
  if (cfg && cfg.sports && cfg.sports.length && sgPlain(cfg.sports).length) u.set("sport", sgPlain(cfg.sports).join(","));      // 3.59.0: Fotos und Diashow kennen keine Statistik-Gruppen: aufgelöst
  if (cfg && cfg.range && cfg.range !== "all") {
    const R = flRange(cfg, "all");
    if (R.kind === "y") u.set("year", String(R.year));
    else {
      if (R.from) u.set("from", R.from);
      if (R.to) u.set("to", R.to);
    }
  }
  if (fix) {
    u.delete("year");
    u.set("from", fix.from);
    u.set("to", fix.to);
  }
  if (c.view === "show" && cfg && cfg.tempo) u.set("sec", String(c.tempo));
  return "slideshow.html?" + u;
}
const erShuffle = a => {
  const l = a.slice();
  for (let i = l.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [l[i], l[j]] = [l[j], l[i]];
  }
  return l;
};
const erCap = p => {
  const d = p.taken_ts ? fmtDatumKurz(slIso(new Date(p.taken_ts * 1000))) : "";
  return `<figcaption>${p.tour_name ? `<b>${esc(p.tour_name)}</b>` : ""}${d ? `<span>${d}</span>` : ""}</figcaption>`;
};
/* Spalten im Raster: so viele, wie bei der gewählten Größe in die Breite passen. Reichen sie nicht für alle Fotos, wird höchstens bis zur Hälfte (mindestens 2) verringert,
   wenn dadurch die letzte Zeile voller wird (6 Fotos: 3 × 2 statt 4 + 2); sind es weniger Fotos als Spalten, bleibt die Größe wie gewählt (rechts bleibt Platz). */
function erFit(g, n, size) {
  const w = g.clientWidth;
  if (!w) return;
  const cols = Math.max(1, Math.floor((w + 8) / (ER_MINW[size] + 8)));
  let best = cols;
  if (n > cols && cols > 2) {
    let bestE = Infinity;
    for (let k = cols; k >= Math.max(2, Math.ceil(cols / 2)); k--) {
      const e = k * Math.ceil(n / k) - n;
      if (e < bestE) {
        best = k;
        bestE = e;
      }
    }
  }
  g.style.setProperty("--erc", String(best));
  g.classList.add("erc");
}
const erKey = e => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), e.currentTarget.click());
const erIcon = {
  prev: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M15 5l-7 7 7 7"/></svg>',
  next: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 5l7 7-7 7"/></svg>',
  pause: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5v14M16 5v14"/></svg>',
  play: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path class="fill" d="M8 5l11 7-11 7z"/></svg>',
};
/* Raster und Streifen: die Fotos als anklickbare Bilder (Lightbox wie überall) */
function erThumbs(box, list, c, o) {
  const px = c.view === "strip" ? 500 : ER_PX[c.size],
    figs = list.map((p, i) => `<figure class="erf"><img loading="lazy" decoding="async"${o.preview ? "" : ' tabindex="0" role="button"'} src="${picSrc(p, px)}" data-i="${i}" alt="${esc(p.tour_name || "Foto")}">${c.caption ? erCap(p) : ""}</figure>`).join("");
  if (c.view === "strip") box.innerHTML = `<div class="ers er-s-${c.size} er-r-${c.ratio}"${o.preview ? "" : ' tabindex="0" role="region" aria-label="Fotos, seitlich scrollbar"'}>${figs}</div>`;
  else {
    box.innerHTML = `<div class="erg er-s-${c.size} er-r-${c.ratio}">${figs}</div>`;
    const g = box.firstChild;
    erFit(g, list.length, c.size);
    if (typeof ResizeObserver === "function") new ResizeObserver(() => erFit(g, list.length, c.size)).observe(g);
  }
  if (o.preview) return;
  bindThumbs(box, list);
  box.querySelectorAll("img[data-i]").forEach(im => (im.onkeydown = erKey));
}
/* Einzelbild-Show: blättert selbst (Tempo einstellbar); Pause bei Maus, Fokus und Berührung, mit eigenem Pause-Knopf; bei „weniger Bewegung“ ohne Automatik und ohne Überblenden */
function erShow(box, list, c, o) {
  const n = list.length, reduce = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  box.innerHTML = `<div class="erp er-h-${c.height} er-r-${c.ratio}">` +
    `<div class="erpv"${o.preview ? "" : ' tabindex="0"'} role="group" aria-label="" aria-live="off">${list.map((p, i) => `<img alt="${esc(p.tour_name || "Foto")}" data-i="${i}" aria-hidden="true">`).join("")}</div>` +
    `<div class="erpbar"><button type="button" class="erbtn erprev" aria-label="Vorheriges Foto" title="Vorheriges Foto">${erIcon.prev}</button>` +
    `<button type="button" class="erbtn erpp" aria-label="Anhalten" title="Anhalten" aria-pressed="false">${erIcon.pause}</button>` +
    `<span class="erpc"></span><button type="button" class="erbtn ernext" aria-label="Nächstes Foto" title="Nächstes Foto">${erIcon.next}</button></div>` +
    (c.caption ? `<div class="erpcap"></div>` : "") + `</div>`;
  const root = box.firstChild, st = root.querySelector(".erpv"), imgs = [...st.querySelectorAll("img")], cnt = root.querySelector(".erpc"), cap = root.querySelector(".erpcap"), pp = root.querySelector(".erpp");
  let i = 0, playing = !reduce && !o.preview, hold = 0, timer = 0, swiped = 0;
  const ld = im => !im.getAttribute("src") && im.setAttribute("src", picSrc(list[+im.dataset.i], 1200));
  const go = k => {
    i = ((k % n) + n) % n;
    imgs.forEach((im, j) => {
      const on = j === i;
      im.classList.toggle("on", on);
      im.setAttribute("aria-hidden", on ? "false" : "true");
      if (on || j === (i + 1) % n) ld(im);
    });
    cnt.textContent = `${i + 1} / ${n}`;
    st.setAttribute("aria-label", window.TL ? window.TL("Foto {} von {}").replace("{}", i + 1).replace("{}", n) : `Foto ${i + 1} von ${n}`);
    if (cap) cap.innerHTML = erCap(list[i]);
  };
  const stop = () => {
    clearInterval(timer);
    timer = 0;
  };
  const start = () => {
    stop();
    if (playing && n > 1) timer = setInterval(() => (!root.isConnected ? stop() : !hold && !document.hidden && go(i + 1)), c.tempo * 1000);
  };
  const paint = () => {
    pp.innerHTML = playing ? erIcon.pause : erIcon.play;
    pp.setAttribute("aria-pressed", playing ? "false" : "true");
    pp.setAttribute("aria-label", playing ? "Anhalten" : "Abspielen");
    pp.title = playing ? "Anhalten" : "Abspielen";
    st.setAttribute("aria-live", playing ? "off" : "polite");
    root.classList.toggle("erpaused", !playing);
  };
  pp.onclick = () => {
    playing = !playing;
    paint();
    start();
  };
  root.querySelector(".erprev").onclick = () => (go(i - 1), start());
  root.querySelector(".ernext").onclick = () => (go(i + 1), start());
  st.addEventListener("pointerenter", e => e.pointerType === "mouse" && (hold |= 1));                  // Maus auf dem Bild: Pause (nicht auf den Knöpfen, sonst bliebe „Abspielen“ wirkungslos)
  st.addEventListener("pointerleave", e => e.pointerType === "mouse" && (hold &= ~1));
  root.addEventListener("focusin", e => e.target.matches(":focus-visible") && (hold |= 2));            // Tastaturfokus im Bedienfeld: Pause (ein Mausklick auf einen Knopf nicht)
  root.addEventListener("focusout", () => (hold &= ~2));
  let x0 = 0, y0 = 0;
  st.addEventListener("pointerdown", e => {
    if (e.pointerType === "touch") hold |= 4;
    x0 = e.clientX;
    y0 = e.clientY;
  });
  const up = e => {
    if (e.pointerType === "touch") hold &= ~4;
    if (e.type !== "pointerup") return;
    const dx = e.clientX - x0, dy = e.clientY - y0;
    if (Math.abs(dx) > 40 && Math.abs(dx) > 1.5 * Math.abs(dy)) {
      swiped = Date.now();
      go(i + (dx < 0 ? 1 : -1));
      start();
    }
  };
  st.addEventListener("pointerup", up);
  st.addEventListener("pointercancel", up);
  if (!o.preview) {
    st.addEventListener("click", () => Date.now() - swiped > 400 && openLb(list, i));
    st.addEventListener("keydown", e => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        go(i + (e.key === "ArrowRight" ? 1 : -1));
        start();
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openLb(list, i);
      }
    });
  }
  if (n < 2) root.querySelectorAll(".erprev,.ernext,.erpp").forEach(b => (b.hidden = true));
  go(0);
  paint();
  start();
}
/* Fotos eintragen (Zufall: neu gezogen, sonst nur neu gemischt); ohne Fotos bleibt die Kachel unsichtbar (in der Vorschau steht ein Hinweis) */
function erPaint(sec, cfg, list, o) {
  const c = erCfg(cfg), box = sec.querySelector(".erb");
  if (!list.length) {
    if (o.preview || o.keep) box.innerHTML = `<p class="mut slnone">${o.preview ? "Keine Fotos mit diesen Einstellungen." : o.none || "Keine Fotos."}</p>`;       // o.keep (Reise-Diashow): die Karte bleibt stehen und sagt, warum sie leer ist
    sec.hidden = !(o.preview || o.keep);
    return;
  }
  sec.hidden = false;
  if (c.view === "show") erShow(box, list, c, o);
  else erThumbs(box, list, c, o);
}
/* 3.54.0: Zufällige Auswahl (auch „an diesem Tag“) bleibt für diesen Tab bis zum nächsten Tag oder bis „Neu mischen“ dieselbe: beim erneuten Öffnen und Neuladen der Übersicht
   dieselben Fotos – der Browser hat sie schon (Adresse mit Version), es gibt keine Bildanfrage. Gemerkt werden nur Kennung, Zeit, Tourname und Version (sessionStorage, beim Abmelden gelöscht). */
const ER_HOLD = "mt_erhold";
function erHold(url, list) {
  const day = slIso(new Date());
  let all = {};
  try {
    all = JSON.parse(sessionStorage.getItem(ER_HOLD) || "{}") || {};
  } catch (e) {}
  if (all.day !== day) all = {day};
  if (list === undefined) return Array.isArray(all[url]) ? all[url] : null;
  all[url] = list.slice(0, 12).map(p => ({id: p.id, v: p.v, taken_ts: p.taken_ts, tour_id: p.tour_id, tour_name: p.tour_name}));
  try {
    sessionStorage.setItem(ER_HOLD, JSON.stringify(all));
  } catch (e) {}
}
async function erLoad(sec, cfg, o = {}) {
  const my = (sec._erTok = (sec._erTok || 0) + 1);
  let list = sec._erList;
  if (!list || !o.mix) {
    const url = erUrl(cfg, o.fix), rnd = /random=true/.test(url);
    list = rnd && !o.fresh ? erHold(url) : null;
    if (!list) {
      try {
        list = await api(url);
      } catch (e) {
        list = [];
      }
      if (!Array.isArray(list)) list = [];
      if (rnd && list.length && !o.preview) erHold(url, list);
    }
    sec._erList = list;
  } else list = erShuffle(list);
  if (my === sec._erTok) erPaint(sec, cfg, list, o);
}
/* Die Kachel als Abschnitt der Übersicht (Standard-Instanz: Kennung hmemsec, Zusatz-Instanz: tlw-<id>); Vorschau im Dialog: ohne Kennung, ohne Bedienung der Fotos */
function erShell(it, o = {}) {
  const cfg = it.cfg || {}, c = erCfg(cfg), title = (cfg.title || "").trim() || "Erinnerungen", fl = erKurz(cfg),
    sec = document.createElement("section");
  sec.className = "hmemsec" + (it.widget ? " tlw" : "") + (o.preview ? " erpvw" : "");
  if (!o.preview) sec.id = it.widget ? "tlw-" + it.id : "hmemsec";
  if (it.widget) {
    sec.dataset.wid = it.id;
    sec.dataset.wtype = it.wtype;
  }
  sec.hidden = !o.preview;
  sec.innerHTML = `<div class="hsh erh"><h2>${esc(title)}</h2>${fl.length ? `<span class="flk">${fl.map(p => `<span>${esc(p)}</span>`).join(", ")}</span>` : ""}<span class="sp"></span>` +
    (c.shuffle ? `<button type="button" class="btn ghost sm ernew">Neu mischen</button>` : "") +
    (c.link ? `<a class="hmore erdia" target="_blank" rel="noopener" href="${esc(erSlideUrl(cfg, o.fix))}">${c.mode === "random" ? "Zufalls-Diashow" : "Diashow starten"}</a>` : "") + `</div><div class="erb"></div>`;
  const nb = sec.querySelector(".ernew");
  if (nb) nb.onclick = () => erLoad(sec, cfg, c.mode === "random" ? {...o, fresh: true} : {...o, mix: true});
  erLoad(sec, cfg, o);
  return sec;
}

/* ---------- Dialog mit Vorschau ---------- */
const erRadio = (name, legend, opts, cur, extra = "") =>
  `<fieldset class="slfs erfs"${extra}><legend>${esc(legend)}</legend><div class="flchips" role="radiogroup">${opts.map(([v, l]) => `<label class="flchip"><input type="radio" name="${name}" value="${esc(v)}"${String(v) === String(cur) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div></fieldset>`;
const erCheck = (name, label, on) => `<label class="slck erck"><input type="checkbox" name="${name}"${on ? " checked" : ""}><span>${esc(label)}</span></label>`;
function erForm(cfg, trip) {
  const c = erCfg(cfg), filt = !!((cfg.sports && cfg.sports.length) || (cfg.range && cfg.range !== "all"));
  return `<form class="slform erform" novalidate>` +
    `<section class="erpvs"><h3 class="erpvh">Vorschau</h3><div class="erpvb" role="status" aria-live="polite"></div></section>` +
    flField({kind: "title", ph: trip ? "Fotos der Reise" : "Erinnerungen"}, cfg, 2) +
    `<details class="erdt" open><summary>Welche Fotos</summary>` + erRadio("er-mode", "Auswahl", trip ? ER_MODES.filter(m => m[0] !== "day") : ER_MODES, c.mode) + erRadio("er-n", "Anzahl", ER_N.map(x => [x, String(x)]), c.n) +
    (trip ? `<p class="mut erhint">Es sind immer die Fotos aus dem Zeitraum der Reise.</p>` : `<details class="erdt erdt2"${filt ? " open" : ""}><summary>Filter: Sportart und Zeitraum</summary>${flField({kind: "sports"}, cfg, 0)}${flField({kind: "range", def: "all"}, cfg, 1)}</details>`) + `</details>` +
    `<details class="erdt" open><summary>Darstellung</summary>` + erRadio("er-view", "Art der Darstellung", ER_VIEWS, c.view) + erRadio("er-ratio", "Seitenverhältnis der Kacheln", ER_RATIOS, c.ratio) +
    `<p class="mut erhint" data-for="show">In der Einzelbild-Show bestimmt die Höhe die Form; „Originalformat“ zeigt das ganze Bild ohne Zuschnitt.</p>` +
    erRadio("er-size", "Größe der Bilder", ER_SIZES, c.size, ' data-for="grid strip"') + erRadio("er-height", "Höhe der Show", ER_HEIGHTS, c.height, ' data-for="show"') +
    erRadio("er-tempo", "Tempo (Sekunden je Bild)", ER_TEMPO.map(x => [x, `${x} s`]), c.tempo, ' data-for="show"') + `</details>` +
    `<details class="erdt" open><summary>Anzeige</summary>` + erCheck("er-caption", "Bildunterschrift (Tourname und Datum)", c.caption) +
    erCheck("er-shuffle", "Knopf „Neu mischen“ (zieht neue Zufallsfotos, sonst mischt er die Reihenfolge)", c.shuffle) + erCheck("er-link", "Link „Diashow starten“", c.link) + `</details>` +
    `<p class="slerr ererr" role="alert"></p><div class="uifoot"><button type="button" class="btn ghost erreset" title="Alle Einstellungen dieser Kachel auf den Standard setzen">Standardwerte</button><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">Speichern</button></div></form>`;
}
/* Formular → Einstellung (nur Abweichungen vom Standard; was zur gewählten Darstellung nicht gehört, wird nicht gespeichert) */
function erRead(form) {
  const out = {}, val = n => (form.querySelector(`input[name="${n}"]:checked`) || {}).value, D = erCfg({});
  if (form.querySelector('[name="f1"]')) {                                   // (die Reise-Diashow hat keinen Filter)
    flRead({kind: "sports"}, form, 0, out);
    flRead({kind: "range", def: "all"}, form, 1, out);
  }
  flRead({kind: "title"}, form, 2, out);
  const mode = val("er-mode"), n = +val("er-n"), view = val("er-view"), ratio = val("er-ratio"), size = val("er-size"), height = val("er-height"), tempo = +val("er-tempo");
  if (mode && mode !== D.mode) out.mode = mode;
  if (n && n !== D.n) out.n = n;
  if (view && view !== D.view) out.view = view;
  if (ratio && ratio !== D.ratio) out.ratio = ratio;
  if (view !== "show" && size && size !== D.size) out.size = size;
  if (view === "show") {
    if (height && height !== D.height) out.height = height;
    if (tempo && tempo !== D.tempo) out.tempo = tempo;
  }
  if (form.querySelector('[name="er-caption"]').checked) out.caption = true;
  if (form.querySelector('[name="er-shuffle"]').checked) out.shuffle = true;
  if (!form.querySelector('[name="er-link"]').checked) out.link = false;
  return out;
}
/* Felder, die nur zu einer Darstellung gehören, ein- oder ausblenden */
function erSync(form) {
  const v = (form.querySelector('input[name="er-view"]:checked') || {}).value || "grid";
  form.querySelectorAll("[data-for]").forEach(e => (e.hidden = !e.dataset.for.split(" ").includes(v)));
}
function erDialog(id, cfg0, trip) {
  const R = trip && window.RS_CUR && window.RS_CUR.tr, fix = R ? {from: R.start, to: R.end} : null;
  slModal(trip ? "Einstellungen: Reise-Diashow" : "Einstellungen: Erinnerungen", (body, close) => {
    const mount = cfg => {
      body.innerHTML = erForm(cfg, trip);
      const form = body.querySelector("form"), pv = form.querySelector(".erpvb");
      let timer = 0;
      const preview = () => {
        pv.textContent = "";
        pv.appendChild(erShell({cfg: erRead(form)}, {preview: true, fix}));
      };
      const later = () => {
        clearTimeout(timer);
        timer = setTimeout(preview, 250);
      };
      flBind(form);
      erSync(form);
      form.addEventListener("input", later);
      form.addEventListener("change", () => {
        erSync(form);
        later();
      });
      form.onclick = e => {
        if (e.target.closest("[data-close]")) close();
        else if (e.target.closest(".erreset")) {
          clearTimeout(timer);
          mount({});
          body.querySelector("input,button").focus();
        }
      };
      form.onsubmit = e => {
        e.preventDefault();
        clearTimeout(timer);
        const out = erRead(form);
        close();
        slSetCfg(id, out);
      };
      preview();
    };
    mount(JSON.parse(JSON.stringify(cfg0 || {})));
  }, "slfe");
}

Object.assign(window.SL_WT, {
  erinn: {
    fam: "uebersicht", cat: "rueck", icon: "cam", name: "Erinnerungen", title: () => "Erinnerungen", multi: true, w: "halb", seiten: ["uebersicht"], defaults: {},
    shell: it => erShell(it), kurz: erKurz, dialog: (id, cfg) => erDialog(id, cfg), fields: [{kind: "erinn"}],
    desc: "Fotos aus deinen Touren als Erinnerung: zufällig, die besten, an diesem Tag in früheren Jahren oder die neuesten, als Raster, Streifen oder Einzelbild-Show mit Link zur passenden Diashow. Anzahl, Sportart, Zeitraum, Bildgröße und Breite sind einstellbar. In der Übersicht steht „Erinnerungen“ schon; hier kannst du weitere Kacheln mit anderen Einstellungen hinzufügen.",
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'),
  },
});
