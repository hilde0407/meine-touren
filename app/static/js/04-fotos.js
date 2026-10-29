/* ---------- Fotos ---------- */
let PH_LIST = [],
  LB_I = 0;
function openLb(list, i) {
  PH_LIST = list;
  LB_I = i;
  showLb();
  $("#lb").classList.add("on");
}
function showLb() {
  const p = PH_LIST[LB_I];
  if (!p) return;
  $("#lbi").src = p.src || `/pic/${p.id}?size=2000`;
  $("#lbc").textContent =
    `${p.tour_name ? p.tour_name + " · " : ""}${new Date(p.taken_ts * 1000).toLocaleString("de-DE", {dateStyle: "long", timeStyle: "short"})} · ${LB_I + 1}/${PH_LIST.length}`;
}
function bindThumbs(box, list) {
  box.querySelectorAll("img[data-i]").forEach(im => (im.onclick = () => openLb(list, +im.dataset.i)));
}
$("#lb").onclick = e => {
  const a = e.target.dataset.a;
  if (a === "next") {
    LB_I = (LB_I + 1) % PH_LIST.length;
    showLb();
  } else if (a === "prev") {
    LB_I = (LB_I - 1 + PH_LIST.length) % PH_LIST.length;
    showLb();
  } else if (a === "close" || e.target.id === "lb") $("#lb").classList.remove("on");
};
addEventListener("keydown", e => {
  if (!$("#lb").classList.contains("on")) return;
  if (e.key === "Escape") $("#lb").classList.remove("on");
  if (e.key === "ArrowRight") {
    LB_I = (LB_I + 1) % PH_LIST.length;
    showLb();
  }
  if (e.key === "ArrowLeft") {
    LB_I = (LB_I - 1 + PH_LIST.length) % PH_LIST.length;
    showLb();
  }
});

VIEWS.photos = async (_, q) => {
  PHINFO = await api("/api/photo-info");
  if (!PHINFO.count) {
    $("#main").innerHTML =
      `<div class="empty"><h2>Noch keine Fotos</h2><p>Importiere einen Ordner mit Bildern – sie werden nach Aufnahmezeit und Aufnahmeort deinen Touren zugeordnet.</p><p><button class="btn" id="pimp">Fotos importieren …</button></p></div>`;
    $("#pimp").onclick = () => photoImportModal();
    return;
  }
  const Y = +(q.get("y") || PHINFO.years[0]);
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Fotos</h2><span class="sub">${nf(PHINFO.count, 0)} Bilder, ${nf(PHINFO.assigned, 0)} einer Tour zugeordnet</span>${PHINFO.undated ? `<span class="chip" style="cursor:default;background:#f6e3b4;color:#5a4300" title="Diese Fotos enthalten keine Aufnahmezeit im Bild. Es wird das Dateidatum benutzt (meist der Exportzeitpunkt); sie werden deshalb nicht automatisch einer Tour zugeordnet. Mit dem Foto-Zeit-Abgleich (mac/foto_zeit_abgleich.py) lässt sich die echte Zeit aus den RAW-Originalen nachtragen.">⚠ ${nf(PHINFO.undated, 0)} ohne Aufnahmezeit</span>` : ""}<span class="sp"></span><button class="btn" id="pimp">Fotos importieren …</button><a class="btn" target="_blank" href="slideshow.html?year=${Y}">Diashow ${Y}</a><a class="btn ghost" target="_blank" href="slideshow.html?random=1">Zufall</a></div>
   <div class="years">${PHINFO.years.map(y => `<button data-y="${y}" class="${y === Y ? "on" : ""}">${y}</button>`).join("")}</div><div id="pg" style="margin-top:26px"></div>`;
  $("#pimp").onclick = () => photoImportModal();
  $(".years").onclick = e => e.target.dataset.y && (location.hash = `#/photos?y=${e.target.dataset.y}`);
  const ph = await api(`/api/photos?year=${Y}&limit=4000`);
  PH_LIST = ph;
  const groups = new Map();
  ph.forEach(p => {
    const k = p.tour_id || "-";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(p);
  });
  $("#pg").innerHTML = [...groups.entries()]
    .map(([k, a]) => {
      const t = BY[k];
      return `<div class="pgroup"><div class="ph"><h3>${t ? `<a href="#/tour/${k}">${esc(t.name)}</a>` : "Ohne Tour"}</h3><span>${t ? dateL(t.date) : new Date(a[0].taken_ts * 1000).toLocaleDateString("de-DE")}, ${a.length} Fotos</span><span class="sp"></span>${t ? `<a class="btn ghost sm" target="_blank" href="slideshow.html?tour=${k}">Diashow</a>` : ""}</div>
    <div class="thumbs">${a.map(p => `<div class="th"><img loading="lazy" src="/pic/${p.id}?size=400" data-i="${ph.indexOf(p)}"><span class="cap">${new Date(p.taken_ts * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}${p.manual === 1 ? " 📌" : ""}</span></div>`).join("")}</div></div>`;
    })
    .join("");
  bindThumbs($("#pg"), ph);
  photoSelect(ph, Y);
};

/* ---------- Fotos manuell zuordnen ---------- */
function photoSelect(ph, Y, o = {box: "#pg", anchor: ".sec .sp"}) {
  const BOX = o.box;
  const sel = new Set();
  let on = false;
  document.body.classList.remove("selmode");
  document.querySelectorAll(".seltb").forEach(x => x.remove());
  const tb = document.createElement("div");
  tb.className = "seltb";
  tb.style.display = "none";
  document.body.appendChild(tb);
  const btn = document.createElement("button");
  btn.className = "btn ghost";
  btn.textContent = "Fotos zuordnen";
  btn.title = "Fotos auswählen: Klick auf ein Foto wählt dieses und alle späteren des Tages, mit Umschalttaste dieses und alle früheren; danach einzelne Fotos per Klick an- oder abwählen";
  $(o.anchor).after(btn);
  if (o.tour) {
    btn.textContent = "Fotos bearbeiten";
    btn.style.marginLeft = "12px";
  }
  const paint = () => {
    document.querySelectorAll(BOX + " img[data-i]").forEach(im => im.classList.toggle("sel", sel.has(ph[+im.dataset.i].id)));
    tb.style.display = on ? "" : "none";
    tb.innerHTML = `<b>${sel.size}</b> ausgewählt ${sel.size ? "" : `<span class="mut" style="font-size:13px">Foto anklicken: dieses und alle späteren des Tages · mit ⇧ Umschalttaste: dieses und alle früheren</span> `}<button class="btn sm" data-a="assign" ${sel.size ? "" : "disabled"}>${o.tour ? "Andere Tour …" : "Einer Tour zuordnen …"}</button>${o.tour ? `<button class="btn alt sm" data-a="rm" ${sel.size ? "" : "disabled"}>Aus dieser Tour entfernen</button>` : `<button class="btn alt sm" data-a="un" ${sel.size ? "" : "disabled"}>Zuordnung lösen</button>`}<button class="btn alt sm" data-a="del" ${sel.size ? "" : "disabled"} style="color:#c0392b;border-color:#c0392b">Löschen …</button><button class="btn alt sm" data-a="off">Fertig</button>`;
    btn.classList.toggle("on", on);
  };
  btn.onclick = () => {
    on = !on;
    if (!on) sel.clear();
    document.body.classList.toggle("selmode", on);
    paint();
  };
  $(BOX).addEventListener(
    "click",
    e => {
      if (!on) return;
      const im = e.target.closest("img[data-i]");
      if (im) {
        e.stopPropagation();
        e.preventDefault();
        const p0 = ph[+im.dataset.i],
          id = p0.id;
        if (!sel.size) {
          // erstes Foto: alle Fotos desselben Tages ab diesem (einschließlich) vorauswählen – mit Umschalttaste alle bis zu diesem
          const dk = x => new Date(x.taken_ts * 1000).toLocaleDateString("de-DE"),
            k = dk(p0),
            i0 = +im.dataset.i,
            after = (x, i) => x.taken_ts > p0.taken_ts || (x.taken_ts === p0.taken_ts && i >= i0),
            before = (x, i) => x.taken_ts < p0.taken_ts || (x.taken_ts === p0.taken_ts && i <= i0);
          ph.forEach((x, i) => {
            if (dk(x) === k && (e.shiftKey ? before(x, i) : after(x, i))) sel.add(x.id);
          });
        } else sel.has(id) ? sel.delete(id) : sel.add(id);
        paint();
        return;
      }
      const g = e.target.closest("[data-g]");
      if (g) {
        const grp = g.closest(".pgroup");
        const ids = [...grp.querySelectorAll("img[data-i]")].map(i => ph[+i.dataset.i].id);
        const all = ids.every(i => sel.has(i));
        ids.forEach(i => (all ? sel.delete(i) : sel.add(i)));
        paint();
      }
    },
    true
  );
  if (!o.tour)
    document.querySelectorAll("#pg .pgroup .ph").forEach(h => {
      const b = document.createElement("button");
      b.className = "btn ghost sm gsel";
      b.dataset.g = "1";
      b.textContent = "Gruppe wählen";
      h.appendChild(b);
    });
  tb.onclick = async e => {
    const a = e.target.dataset.a;
    if (!a) return;
    if (a === "off") return btn.click();
    const ids = [...sel];
    if (a === "del") {
      if (
        !confirm(
          `${ids.length} Foto(s) endgültig löschen?\n\nGelöscht wird die Kopie in Meine Touren (nicht dein Original auf dem Rechner). Die Fotos werden beim nächsten Import nicht erneut übernommen.`
        )
      )
        return;
      await api("/api/photo-delete", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids})});
      PHINFO = await api("/api/photo-info").catch(() => PHINFO);
      return route();
    }
    if (a === "rm") {
      if (
        !confirm(
          `${ids.length} Foto(s) aus dieser Tour entfernen?\n\nSie werden keiner Tour mehr zugeordnet (auch nicht automatisch) und erscheinen unter „Fotos“ bei „Ohne Tour“.`
        )
      )
        return;
      await api("/api/photo-unassign", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({ids, exclude: true}),
      });
      return route();
    }
    if (a === "un") {
      const rs = confirm(
        "Zeitkorrektur dieser Fotos ebenfalls zurücksetzen?\n\nOK = Zuordnung lösen und Zeitkorrektur zurücksetzen\nAbbrechen = nur Zuordnung lösen (danach wieder automatisch nach Zeit)"
      );
      await api("/api/photo-unassign", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({ids, reset_time: rs}),
      });
      return route();
    }
    assignDialog(
      ids.map(i => ph.find(p => p.id === i)),
      async () => route()
    );
  };
  paint();
}
let assignDialog = function (sp, done) {
  const first = sp.slice().sort((a, b) => a.taken_ts - b.taken_ts)[0];
  const tours = TOURS.slice().sort((a, b) => Math.abs(a.start_ts - first.taken_ts) - Math.abs(b.start_ts - first.taken_ts));
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="mbox"><h2>${sp.length} Foto${sp.length > 1 ? "s" : ""} zuordnen</h2>
   <div class="field"><label>Tour (nächstgelegene zuerst)</label><select id="at">${tours.map(t => `<option value="${t.id}">${dateS(t.date)} · ${esc(t.name)} (${sName(t.sport)})</option>`).join("")}</select></div>
   <label class="chk"><input type="checkbox" id="as"> Zeit der Fotos anpassen: Das erste gewählte Foto (${new Date(first.taken_ts * 1000).toLocaleString("de-DE")}) wurde</label>
   <div id="aso" style="margin:6px 0 0 24px;display:none"><input id="am" type="number" value="0" step="5" style="width:80px"> Minuten nach dem Start der Tour aufgenommen.
     <div class="field"><label>Zeitversatz anwenden auf</label><select id="asc"><option value="selected">nur die gewählten Fotos</option><option value="day">alle Fotos desselben Aufnahmetags</option><option value="unassigned">alle noch nicht zugeordneten Fotos</option></select></div>
     <div class="mut" id="ap" style="font-size:14px"></div></div>
   <div class="row" style="margin-top:18px"><button class="btn" id="aok">Zuordnen</button><button class="btn alt" id="ano">Abbrechen</button><span id="aer" class="bad"></span></div></div>`;
  document.body.appendChild(m);
  const upd = () => {
    $("#aso").style.display = $("#as").checked ? "" : "none";
    const t = BY[$("#at").value];
    const off = Math.round(t.start_ts + (+$("#am").value || 0) * 60 - first.taken_ts);
    const a = Math.abs(off),
      h = Math.floor(a / 3600),
      mi = Math.round((a % 3600) / 60);
    $("#ap").textContent = `Zeitversatz: ${off < 0 ? "−" : "+"}${h > 23 ? Math.floor(h / 24) + " Tage " + (h % 24) : h} Std. ${mi} Min.`;
  };
  ["at", "as", "am", "asc"].forEach(i => ($("#" + i).oninput = upd));
  upd();
  $("#ano").onclick = () => m.remove();
  $("#aok").onclick = async () => {
    try {
      const r = await api("/api/photo-assign", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({
          ids: sp.map(p => p.id),
          tour_id: $("#at").value,
          shift: $("#as").checked,
          minutes: +$("#am").value || 0,
          scope: $("#asc").value,
        }),
      });
      m.remove();
      await done(r);
    } catch (e) {
      $("#aer").textContent = e.message;
    }
  };
};

/* ---------- Foto-Upload im Browser ---------- */
function exifDate(buf) {
  // liest DateTimeOriginal aus dem JPEG-Kopf
  const v = new DataView(buf);
  if (v.getUint16(0) !== 0xffd8) return null;
  let o = 2;
  while (o + 4 < v.byteLength) {
    const m = v.getUint16(o),
      len = v.getUint16(o + 2);
    if (m === 0xffe1 && v.getUint32(o + 4) === 0x45786966) {
      const t = o + 10,
        le = v.getUint16(t) === 0x4949,
        g16 = x => v.getUint16(x, le),
        g32 = x => v.getUint32(x, le);
      const ifd = (off, tag) => {
        const n = g16(t + off);
        for (let i = 0; i < n; i++) {
          const e = t + off + 2 + i * 12;
          if (g16(e) === tag) return e;
        }
        return null;
      };
      const e1 = ifd(g32(t + 4), 0x8769);
      if (e1 === null) return null;
      const e2 = ifd(g32(e1 + 8), 0x9003) ?? ifd(g32(e1 + 8), 0x9004);
      if (e2 === null) return null;
      const so = t + g32(e2 + 8);
      let r = "";
      for (let i = 0; i < 19; i++) r += String.fromCharCode(v.getUint8(so + i));
      return r;
    }
    if ((m & 0xff00) !== 0xff00) break;
    o += 2 + len;
  }
  return null;
}
function exifOffset(buf) {
  // Zeitzonen-Versatz der Aufnahme (OffsetTimeOriginal/OffsetTime, z. B. "+00:00") – ohne ihn wäre die Kamerazeit mehrdeutig
  const v = new DataView(buf);
  if (v.getUint16(0) !== 0xffd8) return null;
  let o = 2;
  while (o + 4 < v.byteLength) {
    const m = v.getUint16(o),
      len = v.getUint16(o + 2);
    if (m === 0xffe1 && v.getUint32(o + 4) === 0x45786966) {
      const t = o + 10,
        le = v.getUint16(t) === 0x4949,
        g16 = x => v.getUint16(x, le),
        g32 = x => v.getUint32(x, le);
      const ifd = (off, tag) => {
        const n = g16(t + off);
        for (let i = 0; i < n; i++) {
          const e = t + off + 2 + i * 12;
          if (g16(e) === tag) return e;
        }
        return null;
      };
      const e1 = ifd(g32(t + 4), 0x8769);
      if (e1 === null) return null;
      for (const tag of [0x9011, 0x9010]) {
        const e = ifd(g32(e1 + 8), tag);
        if (e === null) continue;
        const cnt = g32(e + 4),
          so = cnt > 4 ? t + g32(e + 8) : e + 8;
        let r = "";
        for (let i = 0; i < Math.min(6, cnt); i++) r += String.fromCharCode(v.getUint8(so + i));
        if (/^[+-]\d\d:\d\d$/.test(r)) return r;
      }
      return null;
    }
    if ((m & 0xff00) !== 0xff00) break;
    o += 2 + len;
  }
  return null;
}
function exifGps(buf) {
  // Aufnahmeort (Breite, Länge) aus dem JPEG-Kopf
  const v = new DataView(buf);
  if (v.getUint16(0) !== 0xffd8) return null;
  let o = 2;
  while (o + 4 < v.byteLength) {
    const m = v.getUint16(o),
      len = v.getUint16(o + 2);
    if (m === 0xffe1 && v.getUint32(o + 4) === 0x45786966) {
      const t = o + 10,
        le = v.getUint16(t) === 0x4949,
        g16 = x => v.getUint16(x, le),
        g32 = x => v.getUint32(x, le);
      const find = (off, tag) => {
        const n = g16(t + off);
        for (let i = 0; i < n; i++) {
          const e = t + off + 2 + i * 12;
          if (g16(e) === tag) return e;
        }
        return null;
      };
      const eg = find(g32(t + 4), 0x8825);
      if (eg === null) return null;
      const go = g32(eg + 8);
      const ref = tag => {
        const e = find(go, tag);
        return e === null ? null : String.fromCharCode(v.getUint8(e + 8));
      };
      const rat = tag => {
        const e = find(go, tag);
        if (e === null) return null;
        const p = t + g32(e + 8),
          r = i => g32(p + i * 8) / (g32(p + i * 8 + 4) || 1);
        return r(0) + r(1) / 60 + r(2) / 3600;
      };
      const la = rat(2),
        lo = rat(4);
      if (la === null || lo === null || isNaN(la + lo)) return null;
      return [ref(1) === "S" ? -la : la, ref(3) === "W" ? -lo : lo];
    }
    if ((m & 0xff00) !== 0xff00) break;
    o += 2 + len;
  }
  return null;
}
/* ---------- Foto-Import: ein Dialog (auswählen oder ablegen → Vorschau je Aufnahmetag → importieren) ---------- */
const PHOTO_EXT = /\.(jpe?g|png|webp)$/i;
async function filesFromDrop(dt) {
  const ents = [...(dt.items || [])].map(i => (i.webkitGetAsEntry ? i.webkitGetAsEntry() : null)).filter(Boolean); // sofort, danach ist dt leer
  const out = [];
  const walk = async (en, path) => {
    if (en.isFile) await new Promise(r => en.file(f => ((f._rp = path + f.name), out.push(f), r()), r));
    else if (en.isDirectory) {
      const rd = en.createReader();
      let all = [];
      for (;;) {
        const b = await new Promise(r => rd.readEntries(r, () => r([])));
        if (!b.length) break;
        all = all.concat(b);
      }
      for (const c of all) await walk(c, path + en.name + "/");
    }
  };
  if (ents.length) for (const e of ents) await walk(e, "");
  else out.push(...dt.files);
  return out;
}
const shiftTxt = s => {
  if (!s) return "";
  const a = Math.abs(Math.round(s / 60)),
    h = Math.floor(a / 60),
    mi = a % 60;
  return `${s < 0 ? "−" : "+"}${h ? h + " Std. " : ""}${mi ? mi + " Min." : h ? "" : "0 Min."}`.trim();
};
function photoImportModal(o = {}) {
  const m = modal(`<h2 id="pih"></h2><div id="pib"></div>`);
  const q = s => m.querySelector(s);
  let busy = false,
    stop = false;
  m.style.zIndex = 120;
  m.onclick = e => {
    if (e.target === m && !busy) m.remove();
  };
  q(".mbox").style.maxWidth = "720px";
  const close = () => {
    if (busy && !confirm("Der Import läuft noch. Wirklich abbrechen?")) return;
    stop = true;
    m.remove();
    if (/^#\/(photos|tour|admin)/.test(location.hash))
      try {
        route();
      } catch (e) {}
  };
  const body = html => (q("#pib").innerHTML = html);
  const relOf = f => {
    const full = f._rp || f.webkitRelativePath || "",
      p = full.includes("/") ? full.split("/").slice(1).join("/") : `einzeln/${Math.floor(f.lastModified / 1000)}_${f.name}`,
      mm = p.match(/^(.*)\.([^.]+)$/),
      base = mm ? mm[1] : p,
      ext = mm ? mm[2].toLowerCase() : "";
    return /^jpe?g$/.test(ext) || !ext ? base : `${base}~${ext}`; // andere Endungen bekommen einen eigenen Namen (keine Kollision mit gleichnamigem JPG)
  };
  const start = () => {
    q("#pih").textContent = o.tour ? `Fotos zu „${o.tour.name}“ hinzufügen` : "Fotos importieren";
    body(`<div id="pdz" style="border:2px dashed var(--ink);border-radius:8px;padding:30px 16px;text-align:center;margin:12px 0"><b>Ordner oder Fotos hierher ziehen</b>
      <div class="mut" style="margin:8px 0 16px;font-size:14px">JPG, PNG oder WebP – du musst nichts vorsortieren. Die Fotos werden nach Aufnahmezeit und Aufnahmeort den Touren zugeordnet; du siehst vor dem Import, was wohin kommt. Deine Originale bleiben unverändert, importiert wird eine verkleinerte Kopie.</div>
      <div class="row" style="justify-content:center"><button class="btn" id="pdirb">Ordner wählen …</button><button class="btn alt" id="pfilb">Einzelne Fotos wählen …</button></div></div>
      <input type="file" id="pdir" webkitdirectory multiple hidden><input type="file" id="pfil" accept="image/jpeg,image/png,image/webp" multiple hidden>
      <div class="row"><span class="sp"></span><button class="btn ghost" id="pcx">Schließen</button></div>`);
    const dz = q("#pdz");
    q("#pdirb").onclick = () => q("#pdir").click();
    q("#pfilb").onclick = () => q("#pfil").click();
    q("#pcx").onclick = close;
    q("#pdir").onchange = q("#pfil").onchange = e => {
      const fs = [...e.target.files];
      e.target.value = "";
      if (fs.length) analyse(fs);
    };
    ["dragenter", "dragover"].forEach(ev =>
      dz.addEventListener(ev, e => {
        e.preventDefault();
        dz.style.background = "#f6e3b455";
      })
    );
    dz.addEventListener("dragleave", () => (dz.style.background = ""));
    dz.addEventListener("drop", async e => {
      e.preventDefault();
      dz.style.background = "";
      const fs = await filesFromDrop(e.dataTransfer);
      if (fs.length) analyse(fs);
    });
  };
  const analyse = async (all, withGone = false) => {
    busy = true;
    try {
      const files = all.filter(f => PHOTO_EXT.test(f.name) && !f.name.startsWith(".")),
        other = all.length - files.length,
        heic = all.filter(f => /\.hei[cf]$/i.test(f.name)).length;
      if (!files.length) {
        busy = false;
        body(`<p>Es wurden keine JPG-, PNG- oder WebP-Bilder gefunden${heic ? ` (${heic} HEIC-Bilder: der Browser kann sie nicht verkleinern – bitte vorher als JPG exportieren)` : ""}.</p><div class="row"><button class="btn" id="pback">Zurück</button></div>`);
        q("#pback").onclick = start;
        return;
      }
      body(`<p id="ptxt0">Fotos werden geprüft …</p>`);
      const lib = await api("/api/photo-library?split=1"),
        have = new Set(lib.have),
        gone = new Set(lib.deleted),
        fresh = files.filter(f => !have.has(relOf(f)) && (withGone || !gone.has(relOf(f)))),
        deleted = withGone ? 0 : files.filter(f => !have.has(relOf(f)) && gone.has(relOf(f))).length,
        items = [];
      let nodate = 0;
      for (let i = 0; i < fresh.length; i++) {
        if (i % 40 === 0) {
          q("#ptxt0").textContent = `Aufnahmezeiten werden gelesen … ${i} / ${fresh.length}`;
          await new Promise(r => setTimeout(r));
        }
        const f = fresh[i],
          hd = f.type === "image/jpeg" ? await f.slice(0, 262144).arrayBuffer() : null,
          d = new Date(f.lastModified);
        let ed = null,
          gp = null;
        f._o = "";
        try {
          ed = hd ? exifDate(hd) : null;
          f._o = (ed && hd && exifOffset(hd)) || "";
        } catch (e) {}
        try {
          gp = hd ? exifGps(hd) : null;
        } catch (e) {}
        if (!ed) nodate++;
        f._t = ed || `${d.getFullYear()}:${pad2(d.getMonth() + 1)}:${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
        f._gps = gp;
        items.push({k: i, t: f._t, o: f._o, lat: gp ? gp[0] : null, lng: gp ? gp[1] : null});
      }
      const info = {total: files.length, dup: files.length - fresh.length - deleted, deleted, other, heic, nodate, all};
      if (!fresh.length) {
        busy = false;
        body(`<p><b>Nichts zu importieren:</b> ${info.dup ? `${info.dup} Bilder sind schon in der Bibliothek` : ""}${info.dup && deleted ? " und " : ""}${deleted ? `${deleted} Bilder hast du früher gelöscht – sie werden deshalb nicht erneut übernommen` : ""}.</p>
          <div class="row">${deleted ? `<button class="btn" id="pre">Die ${deleted} gelöschten Fotos erneut importieren</button>` : ""}<button class="btn alt" id="pback">Anderen Ordner wählen</button><button class="btn ghost" id="pcx">Schließen</button></div>`);
        if (deleted) q("#pre").onclick = () => analyse(all, true);
        q("#pback").onclick = start;
        q("#pcx").onclick = close;
        return;
      }
      q("#ptxt0").textContent = "Passende Touren werden gesucht …";
      const plan = await api("/api/photo-plan", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({items, tour: o.tour ? o.tour.id : null}),
      });
      busy = false;
      preview(fresh, plan, info);
    } catch (e) {
      busy = false;
      console.error(e);
      body(`<p class="bad">Fehler beim Prüfen: ${esc((e && e.message) || String(e))}</p><div class="row"><button class="btn" id="pback">Zurück</button></div>`);
      q("#pback").onclick = start;
    }
  };
  const preview = (fresh, plan, info) => {
    const days = plan.days,
      rows = days.map((d, i) => {
        const ch = [];
        if (d.status === "ok" && !o.tour) ch.push({v: "time", t: `Nach Uhrzeit zuordnen${d.names && d.names.length ? " → " + d.names.join(", ") : ""}${d.matched < d.n ? ` (${d.matched} von ${d.n} passen zeitlich)` : ""}`});
        d.options.forEach((p, j) =>
          ch.push({
            v: "o" + j,
            t: `${p.name} · ${p.start} · ${p.matched} von ${d.n} passen${p.shift_s ? ` · Zeit ${shiftTxt(p.shift_s)}${p.by_gps ? " (per GPS)" : ""}` : ""}${p.gap_min ? ` · nächstes Foto ${p.gap_min} min außerhalb` : ""}${p.dist_km != null ? ` · ${p.dist_km} km vom Aufnahmeort` : ""}`,
          })
        );
        ch.push({v: "none", t: "Ohne Tour importieren (erscheint unter „Ohne Tour“)"});
        ch.push({v: "skip", t: "Nicht importieren"});
        let def = ch.some(c => c.v === "time") ? "time" : null;
        if (!def && d.options.length && (o.tour || d.options[0].matched >= d.n * 0.5)) def = "o0";
        if (!def) def = plan.only ? "skip" : "none";
        return {d, ch, def};
      });
    q("#pih").textContent = o.tour ? `Fotos zu „${o.tour.name}“ hinzufügen` : "Fotos importieren";
    body(`<p>${info.total} Bilder gefunden, davon <b>${fresh.length}</b> zu importieren${info.dup ? ` (${info.dup} schon vorhanden)` : ""}${info.deleted ? ` · <a href="#" id="pre">${info.deleted} früher gelöschte ebenfalls importieren</a>` : ""}.${info.nodate ? ` <span class="mut">${info.nodate} ohne Aufnahmezeit im Bild – dort gilt das Dateidatum.</span>` : ""}${info.heic ? ` <span class="mut">${info.heic} HEIC-Bilder werden übersprungen (bitte als JPG exportieren).</span>` : ""}</p>
      <p class="mut" style="font-size:14px">So werden die Fotos nach Aufnahmetag zugeordnet. Pro Tag kannst du die Auswahl ändern.</p>
      ${rows
        .map(
          (r, i) => `<div class="panel" style="margin:10px 0"><div style="display:flex;gap:12px;flex-wrap:wrap;align-items:baseline"><b>${r.d.day.split("-").reverse().join(".")}</b><span>${r.d.n} Foto${r.d.n > 1 ? "s" : ""}</span>${r.d.gps ? `<span class="mut" style="font-size:13px">${r.d.gps} mit Aufnahmeort</span>` : ""}${r.d.status === "ask" && r.d.reason ? `<span class="mut" style="font-size:13px">· ${esc(r.d.reason)}</span>` : ""}</div>
          <select data-r="${i}" style="width:100%;margin-top:6px">${r.ch.map(c => `<option value="${c.v}" ${c.v === r.def ? "selected" : ""}>${esc(c.t)}</option>`).join("")}</select></div>`
        )
        .join("")}
      <div class="row" style="margin-top:14px"><button class="btn" id="pigo">Importieren</button><button class="btn ghost" id="pcx">Abbrechen</button><span class="sp"></span><span class="mut" id="pisum"></span></div>`);
    if (q("#pre"))
      q("#pre").onclick = e => {
        e.preventDefault();
        analyse(info.all, true);
      };
    const val = i => q(`select[data-r="${i}"]`).value;
    const count = () => {
      const n = rows.reduce((a, r, i) => a + (val(i) === "skip" ? 0 : r.d.n), 0);
      q("#pisum").textContent = `${n} von ${fresh.length} Fotos werden importiert`;
      q("#pigo").disabled = !n;
      q("#pigo").textContent = n ? `${n} Foto${n > 1 ? "s" : ""} importieren` : "Nichts ausgewählt";
    };
    m.querySelectorAll("select[data-r]").forEach(se => (se.onchange = count));
    count();
    q("#pcx").onclick = close;
    q("#pigo").onclick = () => {
      const todo = [];
      rows.forEach((r, i) => {
        const v = val(i);
        r.d.keys.forEach(k => {
          const f = fresh[k];
          f._tour = "";
          f._shift = 0;
          f._force = false;
          if (v === "skip") return;
          if (v === "none") f._force = true;
          else if (v[0] === "o") {
            const p = r.d.options[+v.slice(1)];
            f._tour = p.tour;
            f._shift = p.shift_s || 0;
          }
          todo.push(f);
        });
      });
      upload(todo);
    };
  };
  const upload = async todo => {
    busy = true;
    stop = false;
    q("#pih").textContent = "Fotos werden importiert …";
    body(`<div class="stack" style="height:10px"><div id="pbar" style="width:0;background:var(--acc)"></div></div>
      <div class="row" style="margin-top:8px"><span id="ptxt" class="mut"></span><span class="sp"></span><button class="btn alt sm" id="pstop">Abbrechen</button></div>`);
    q("#pstop").onclick = () => (stop = true);
    const before = PHINFO ? PHINFO.assigned : 0;
    let done = 0,
      dup = 0,
      skipped = 0,
      fail = 0;
    const failed = [],
      mx = +s_max() || 2200,
      qu = (+s_q() || 82) / 100,
      t0 = Date.now();
    const one = async f => {
      try {
        const bmp = await createImageBitmap(f, {imageOrientation: "from-image"}),
          k = Math.min(1, mx / Math.max(bmp.width, bmp.height));
        const c = document.createElement("canvas");
        c.width = Math.round(bmp.width * k);
        c.height = Math.round(bmp.height * k);
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        bmp.close();
        const blob = await new Promise(r => c.toBlob(r, "image/jpeg", qu));
        const fd = new FormData();
        fd.append("file", blob, "x.jpg");
        fd.append("rel", relOf(f));
        fd.append("taken", f._t);
        if (f._o) fd.append("offset", f._o);
        if (f._tour) {
          fd.append("tour", f._tour);
          fd.append("shift_s", f._shift || 0);
        }
        if (f._force) fd.append("force", "1");
        if (f._gps) {
          fd.append("lat", f._gps[0]);
          fd.append("lng", f._gps[1]);
        }
        fd.append("mtime", Math.floor(f.lastModified / 1000));
        const r = await api("/api/photo-upload", {method: "POST", body: fd});
        if (r && r.duplicate) dup++;
        else if (r && r.skipped) skipped++;
        else done++;
      } catch (e) {
        fail++;
        if (failed.length < 3) failed.push(f.name);
      }
      const n = done + dup + skipped + fail,
        eta = n ? Math.round((((Date.now() - t0) / n) * (todo.length - n)) / 1000) : 0;
      if (!q("#pbar")) return;
      q("#pbar").style.width = (n / todo.length) * 100 + "%";
      q("#ptxt").textContent = `${n} / ${todo.length}${fail ? ` · ${fail} Fehler` : ""} · noch ca. ${Math.floor(eta / 60)} min`;
    };
    const queue = todo.slice();
    await Promise.all(
      [0, 1, 2].map(async () => {
        while (queue.length && !stop) await one(queue.shift());
      })
    );
    const sum = `${done} importiert${dup ? `, ${dup} doppelt (schon vorhanden)` : ""}${skipped ? `, ${skipped} ohne passende Strecke übersprungen` : ""}${fail ? `, ${fail} Fehler${failed.length ? " (z. B. " + failed.join(", ") + ")" : ""}` : ""}${stop ? " – abgebrochen" : ""}`;
    if (!q("#ptxt")) return;
    q("#ptxt").textContent = `${sum}. Bibliothek wird eingelesen …`;
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    let started = false;
    for (let i = 0; i < 30 && !started; i++) {
      try {
        await api("/api/jobs/photos", {method: "POST"});
        started = true;
      } catch (e) {
        await sleep(2000);
      }
    }
    let ok = started;
    if (started)
      for (let i = 0; i < 900; i++) {
        await sleep(1500);
        if (!q("#ptxt")) return;
        const j = await api("/api/jobs").catch(() => null);
        if (j && j.running) {
          q("#ptxt").textContent = `${sum}. Bibliothek wird eingelesen … ${j.progress || ""}`;
          continue;
        }
        break;
      }
    busy = false;
    PHINFO = await api("/api/photo-info").catch(() => PHINFO);
    const gain = PHINFO ? PHINFO.assigned - before : 0;
    q("#pih").textContent = ok ? "Import abgeschlossen" : "Import fast abgeschlossen";
    body(`<p>${ok ? "✓" : "⚠"} <b>${sum}.</b></p>${ok ? `<p>${gain > 0 ? `<b>${gain}</b> Fotos wurden Touren zugeordnet.` : "Es wurden keine Fotos automatisch einer Tour zugeordnet."}${PHINFO && PHINFO.count - PHINFO.assigned > 0 ? ` ${nf(PHINFO.count - PHINFO.assigned, 0)} Fotos sind „ohne Tour“ – unter Fotos → „Fotos zuordnen“ lassen sie sich Touren zuweisen, in der Tour per „Zeit per GPS prüfen“ korrigieren.` : ""}</p>` : `<p>Das Einlesen konnte nicht gestartet werden – bitte in der Verwaltung „Bibliothek neu einlesen“ ausführen.</p>`}
      <div class="row"><a class="btn" href="#/photos" id="pgo">Fotos ansehen</a><button class="btn ghost" id="pcx">Schließen</button></div>`);
    q("#pcx").onclick = close;
    q("#pgo").onclick = () => {
      stop = true;
      m.remove();
    };
  };
  start();
  return m;
}
async function folderUpload() {
  const b = $("#photoimp");
  if (b) b.onclick = () => photoImportModal();
}
const s_max = () => document.querySelector('[data-k="photo_max_side"]')?.value,
  s_q = () => document.querySelector('[data-k="photo_quality"]')?.value;

/* Zeit der Fotos per Aufnahmeort mit der Strecke abgleichen (Kamerauhr falsch gestellt) */
async function gpsAlign(t) {
  const r = await api(`/api/photo-offset?tour_id=${encodeURIComponent(t.id)}`);
  if (!r.ok) return alert("Zeitabgleich nicht möglich:\n\n" + r.reason);
  if (r.aligned) return alert(`Die Zeiten der Fotos passen zur Strecke (${r.n} von ${r.of} Fotos mit Aufnahmeort geprüft).`);
  if (
    !confirm(
      `Die Kamerauhr scheint ${shiftTxt(Math.abs(r.delta_s)).replace("+", "")} ${r.delta_s > 0 ? "nachzugehen" : "vorzugehen"}.\n\nAus dem Aufnahmeort von ${r.n} von ${r.of} Fotos ergibt sich eine Korrektur von ${shiftTxt(r.delta_s)}. Die Fotos aus diesem Zeitraum werden korrigiert und dieser Tour zugeordnet.\n\nÜbernehmen?`
    )
  )
    return;
  await api("/api/photo-offset", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({tour_id: t.id, delta_s: r.delta_s, ids: r.ids})});
  route();
}
