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
      `<div class="empty"><h2>Noch keine Fotos</h2><p>Lade unter <a href="#/admin"><b>Verwaltung, Fotos</b></a> einen Ordner mit Bildern hoch.</p></div>`;
    return;
  }
  const Y = +(q.get("y") || PHINFO.years[0]);
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Fotos</h2><span class="sub">${nf(PHINFO.count, 0)} Bilder, ${nf(PHINFO.assigned, 0)} einer Tour zugeordnet</span>${PHINFO.undated ? `<span class="chip" style="cursor:default;background:#f6e3b4;color:#5a4300" title="Diese Fotos enthalten keine Aufnahmezeit im Bild. Es wird das Dateidatum benutzt (meist der Exportzeitpunkt); sie werden deshalb nicht automatisch einer Tour zugeordnet. Mit dem Foto-Zeit-Abgleich (mac/foto_zeit_abgleich.py) lässt sich die echte Zeit aus den RAW-Originalen nachtragen.">⚠ ${nf(PHINFO.undated, 0)} ohne Aufnahmezeit</span>` : ""}<span class="sp"></span><a class="btn" target="_blank" href="slideshow.html?year=${Y}">Diashow ${Y}</a><a class="btn ghost" target="_blank" href="slideshow.html?random=1">Zufall</a></div>
   <div class="years">${PHINFO.years.map(y => `<button data-y="${y}" class="${y === Y ? "on" : ""}">${y}</button>`).join("")}</div><div id="pg" style="margin-top:26px"></div>`;
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
function tourChoice(days) {
  // Rückfrage: welche Tour gehört zu den Fotos dieses Tages?
  return new Promise(res => {
    const m =
      modal(`<h2>Welche Tour gehört zu diesen Fotos?</h2><p class="mut">Bei diesen Aufnahmetagen ist die Zuordnung nicht eindeutig. Vorschläge berücksichtigen Zeitverschiebungen (z. B. Kamera noch auf deutscher Zeit im Ausland) und den Aufnahmeort.</p>
      ${days
        .map(
          (
            d,
            i
          ) => `<div class="panel" style="margin:12px 0"><h3 style="margin:0 0 6px">${d.day.split("-").reverse().join(".")} · ${d.n} Foto${d.n > 1 ? "s" : ""}</h3><div class="mut" style="margin-bottom:6px">${esc(d.reason)}</div>
        ${d.matched ? `<label style="display:block;margin:4px 0"><input type="radio" name="d${i}" value="-3" ${d.single && d.options.length ? "" : "checked"}> Nach Uhrzeit zuordnen (nur die ${d.matched} passenden Fotos importieren)</label>` : ""}${d.options.map((o, j) => `<label style="display:block;margin:4px 0"><input type="radio" name="d${i}" value="${j}" ${j === 0 && (d.single || !d.matched) ? "checked" : ""}> <b>${esc(o.name)}</b> · ${o.start} Uhr · ${nf(o.km, 1)} km${o.shift_h ? ` · Zeitverschiebung ${o.shift_h > 0 ? "+" : ""}${o.shift_h} h` : ""} · ${o.matched} von ${d.n} Fotos passen${o.gap_min ? ` · nächstes Foto ${o.gap_min} min außerhalb der Aufzeichnung` : ""}${o.dist_km != null ? ` · ${o.dist_km} km vom Aufnahmeort` : ""}</label>`).join("")}
        <label style="display:block;margin:4px 0"><input type="radio" name="d${i}" value="-2"> Trotzdem importieren, ohne Tour (erscheint unter „Ohne Tour“)</label>
        <label style="display:block;margin:4px 0"><input type="radio" name="d${i}" value="-1" ${d.options.length || d.matched ? "" : "checked"}> Nicht importieren</label></div>`
        )
        .join("")}
      <div class="row" style="margin-top:12px"><button class="btn" id="tcok">Übernehmen</button><button class="btn ghost" id="tccx">Abbrechen</button></div>`);
    m.querySelector("#tccx").onclick = () => {
      m.remove();
      res(null);
    };
    m.querySelector("#tcok").onclick = () => {
      const out = days.map((d, i) => {
        const v = +m.querySelector(`input[name=d${i}]:checked`).value;
        return v === -2 ? {tour: "", shift_h: 0, force: true} : v === -3 ? {bytime: true} : v < 0 ? null : d.options[v];
      });
      m.remove();
      res(out);
    };
  });
}
async function folderUpload() {
  const inp = $("#pdir");
  if (!inp) return;
  let stop = false;
  $("#pdirb").onclick = () => inp.click();
  $("#pstop").onclick = () => (stop = true);
  inp.onchange = async () => {
    try {
      await uploadFolder(inp);
    } catch (e) {
      console.error(e);
      $("#ptxt") && ($("#ptxt").textContent = "Fehler: " + e);
      alert("Der Foto-Upload ist abgebrochen: " + ((e && e.message) || e));
    }
  };
  const uploadFolder = async inp => {
    const files = [...inp.files].filter(f => /\.(jpe?g|png|webp)$/i.test(f.name) && !f.name.startsWith("."));
    inp.value = "";
    if (!files.length) return alert("Im gewählten Ordner wurden keine JPG/PNG-Bilder gefunden.");
    const have = new Set(await api("/api/photo-library"));
    const rel = f => {
      const p = (f.webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name,
        m = p.match(/^(.*)\.([^.]+)$/);
      const base = m ? m[1] : p,
        ext = m ? m[2].toLowerCase() : "";
      return /^jpe?g$/.test(ext) || !ext ? base : `${base}~${ext}`;
    }; // andere Endungen bekommen einen eigenen Namen (keine Kollision mit gleichnamigem JPG)
    const pw = await api("/api/photo-windows").catch(() => ({only: false, windows: []}));
    const fresh = files.filter(f => !have.has(rel(f)));
    let todo = fresh,
      notrack = 0;
    if (pw.only && fresh.length) {
      $("#pup2").style.display = "";
      $("#ptxt").textContent = `Aufnahmezeiten von ${fresh.length} Fotos werden geprüft …`;
      const items = [];
      for (let i = 0; i < fresh.length; i++) {
        if (i % 50 === 0) {
          $("#ptxt").textContent = `Aufnahmezeiten werden geprüft … ${i} / ${fresh.length}`;
          await new Promise(r => setTimeout(r));
        }
        const f = fresh[i],
          hd = f.type === "image/jpeg" ? await f.slice(0, 262144).arrayBuffer() : null,
          d = new Date(f.lastModified);
        let ed = null,
          gp = null;
        try {
          ed = hd ? exifDate(hd) : null;
        } catch (e) {}
        try {
          gp = hd ? exifGps(hd) : null;
        } catch (e) {}
        f._t =
          ed ||
          `${d.getFullYear()}:${pad2(d.getMonth() + 1)}:${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
        f._gps = gp;
        items.push({k: i, t: f._t, lat: gp ? gp[0] : null, lng: gp ? gp[1] : null});
      }
      $("#ptxt").textContent = "Passende Touren werden gesucht …";
      const plan = await api("/api/photo-plan", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({items}),
      });
      const ask = plan.days.filter(d => d.status === "ask"),
        ok = new Set(plan.days.filter(d => d.status === "ok").flatMap(d => d.keys));
      const picks = ask.length ? await tourChoice(ask) : [];
      if (ask.length && picks === null) return;
      const keep = new Set();
      plan.days
        .filter(d => d.status === "ok")
        .forEach(d =>
          d.keys.forEach(k => {
            const f = fresh[k],
              t = Math.floor(
                new Date(
                  +f._t.slice(0, 4),
                  +f._t.slice(5, 7) - 1,
                  +f._t.slice(8, 10),
                  +f._t.slice(11, 13),
                  +f._t.slice(14, 16),
                  +f._t.slice(17, 19)
                ) / 1000
              );
            if (pw.windows.some(([x, y]) => t >= x - 3600 && t <= y + 3600)) keep.add(k);
          })
        );
      ask.forEach((d, i) => {
        const p = picks[i];
        if (p && p.bytime)
          d.keys.forEach(k => {
            const f = fresh[k],
              t = Math.floor(
                new Date(
                  +f._t.slice(0, 4),
                  +f._t.slice(5, 7) - 1,
                  +f._t.slice(8, 10),
                  +f._t.slice(11, 13),
                  +f._t.slice(14, 16),
                  +f._t.slice(17, 19)
                ) / 1000
              );
            if (pw.windows.some(([x, y]) => t >= x - 3600 && t <= y + 3600)) keep.add(k);
          });
        else if (p)
          d.keys.forEach(k => {
            fresh[k]._tour = p.tour;
            fresh[k]._shift = p.shift_h * 3600;
            fresh[k]._force = !!p.force;
            keep.add(k);
          });
      });
      todo = fresh.filter((f, k) => keep.has(k));
      notrack = fresh.length - todo.length;
    }
    $("#ptxt").textContent = "";
    if (!todo.length) {
      $("#pup2").style.display = "none";
      alert(
        `${files.length} Bilder gefunden – es gibt nichts zu übernehmen:\n\n• ${files.length - fresh.length} sind schon in der Bibliothek (oder wurden früher gelöscht)\n• ${notrack} haben keine passende GPS-Strecke und wurden nicht übernommen${notrack ? "\n\nTipp: Beim nächsten Mal bei der Rückfrage „Trotzdem importieren, ohne Tour“ wählen, oder in den Bildeinstellungen photo_only_tracked auf 0 setzen." : ""}`
      );
      return;
    }
    if (
      !confirm(
        `${files.length} Bilder gefunden, davon ${fresh.length} neu${notrack ? `, ${notrack} ohne passende GPS-Strecke werden übersprungen` : ""}. ${todo.length} jetzt verkleinern und hochladen?`
      )
    )
      return;
    $("#pup2").style.display = "";
    let done = 0,
      fail = 0;
    const mx = +s_max() || 2200,
      q = (+s_q() || 82) / 100,
      t0 = Date.now();
    stop = false;
    const one = async f => {
      try {
        let head = null;
        try {
          head = f.type === "image/jpeg" ? exifDate(await f.slice(0, 262144).arrayBuffer()) : null;
        } catch (e) {}
        const d = new Date(f.lastModified),
          taken =
            head ||
            `${d.getFullYear()}:${pad2(d.getMonth() + 1)}:${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
        const bmp = await createImageBitmap(f, {imageOrientation: "from-image"}),
          k = Math.min(1, mx / Math.max(bmp.width, bmp.height));
        const c = document.createElement("canvas");
        c.width = Math.round(bmp.width * k);
        c.height = Math.round(bmp.height * k);
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        bmp.close();
        const blob = await new Promise(r => c.toBlob(r, "image/jpeg", q));
        const fd = new FormData();
        fd.append("file", blob, "x.jpg");
        fd.append("rel", rel(f));
        fd.append("taken", taken);
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
        await api("/api/photo-upload", {method: "POST", body: fd});
        done++;
      } catch (e) {
        fail++;
      }
      const n = done + fail,
        eta = n ? Math.round((((Date.now() - t0) / n) * (todo.length - n)) / 1000) : 0;
      $("#pbar").style.width = (n / todo.length) * 100 + "%";
      $("#ptxt").textContent = `${n} / ${todo.length}${fail ? ` · ${fail} Fehler` : ""} · noch ca. ${Math.floor(eta / 60)} min`;
    };
    const queue = todo.slice();
    await Promise.all(
      [0, 1, 2].map(async () => {
        while (queue.length && !stop) await one(queue.shift());
      })
    );
    $("#ptxt").textContent =
      `${stop ? "Abgebrochen" : "Fertig"}: ${done} hochgeladen${fail ? `, ${fail} Fehler` : ""}. Bibliothek wird eingelesen …`;
    const sum = `${stop ? "Abgebrochen" : "Fertig"}: ${done} hochgeladen${fail ? `, ${fail} Fehler` : ""}.`;
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
    if (!started) {
      $("#ptxt").textContent = sum + " Einlesen konnte nicht gestartet werden – bitte in der Verwaltung „Fotos indizieren“ ausführen.";
      return;
    }
    for (let i = 0; i < 900; i++) {
      await sleep(1500);
      if (!$("#ptxt")) return;
      const j = await api("/api/jobs").catch(() => null);
      if (j && j.running) {
        $("#ptxt").textContent = `${sum} Bibliothek wird eingelesen … ${j.progress || ""}`;
        continue;
      }
      break;
    }
    $("#ptxt").textContent = `✓ ${sum} Bibliothek ist eingelesen und den Touren zugeordnet – du kannst den Dialog schließen.`;
    if (location.hash.startsWith("#/photos") || location.hash.startsWith("#/tour"))
      setTimeout(() => {
        try {
          route();
        } catch (e) {}
      }, 500);
  };
}
const s_max = () => document.querySelector('[data-k="photo_max_side"]')?.value,
  s_q = () => document.querySelector('[data-k="photo_quality"]')?.value;
