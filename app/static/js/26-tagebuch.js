/* =====================  Tagebuch: Sterne · Sicherheitsnotiz (Ski/Schneeschuh) · Vergleich derselben Strecke  ===================== */
const SAFE_GEAR = [["lvs", "LVS"], ["sonde", "Sonde"], ["schaufel", "Schaufel"], ["helm", "Helm"], ["airbag", "Airbag"], ["erste-hilfe", "Erste Hilfe"], ["biwaksack", "Biwaksack"], ["stirnlampe", "Stirnlampe"]];
const AVAL = {1: ["#5cb85c", "gering"], 2: ["#ffeb3b", "mäßig"], 3: ["#ff9800", "erheblich"], 4: ["#f44336", "groß"], 5: ["#7b1111", "sehr groß"]};
const safetySport = s => ["skitour", "skialpin", "snowshoe", "mountaineering"].includes(s);
const post26 = o => ({method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(o)});

/* Größe eines Textfelds merken (pro Gerät/Browser) und beim nächsten Öffnen wiederherstellen */
function rememberSize(el, key) {
  if (!el || el.dataset.rs) return;
  el.dataset.rs = "1";
  const K = "size:" + key;
  try {
    const v = JSON.parse(localStorage.getItem(K) || "null");
    if (v && v.h >= 40) el.style.height = v.h + "px";
    if (v && v.w >= 120) el.style.width = Math.min(v.w, el.parentElement ? el.parentElement.clientWidth || v.w : v.w) + "px";
  } catch (e) {}
  // Box so hoch machen, dass der ganze Text zu lesen ist (nie kleiner als die gemerkte Größe)
  const fit = () => {
    const need = el.scrollHeight + 4;
    if (el.offsetHeight && need > el.offsetHeight) el.style.height = need + "px";
  };
  fit();
  el.addEventListener("input", fit);
  let last = el.offsetHeight + "x" + el.offsetWidth,
    tm = null;
  if (!window.ResizeObserver) return;
  new ResizeObserver(() => {
    clearTimeout(tm);
    tm = setTimeout(() => {
      const cur = el.offsetHeight + "x" + el.offsetWidth;
      if (cur === last || !el.offsetHeight) return;
      last = cur;
      try {
        localStorage.setItem(K, JSON.stringify({h: el.offsetHeight, w: el.offsetWidth}));
      } catch (e) {}
    }, 400);
  }).observe(el);
}

const _tour26 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour26(...a);
  const t = BY[a[0]],
    w = $("#ewarn");
  if (!t || !w) return;
  rememberSize($("#note"), "note");
  /* ---- Sterne ---- */
  if (!$("#starrow")) {
    w.insertAdjacentHTML("beforebegin", `<div class="starrow" id="starrow"></div>`);
    const drawStars = () => {
      $("#starrow").innerHTML = `<span class="mut">Meine Bewertung:</span>${[1, 2, 3, 4, 5].map(n => `<button type="button" class="st ${n <= (t.stars || 0) ? "on" : ""}" data-n="${n}" title="${n} Stern${n > 1 ? "e" : ""}" aria-label="${n} Sterne">★</button>`).join("")}${t.stars ? `<button type="button" class="btn ghost sm" id="stclr" title="Bewertung entfernen">✕</button>` : ""}`;
      $("#starrow").querySelectorAll(".st").forEach(b => (b.onclick = () => setStars(+b.dataset.n === t.stars ? 0 : +b.dataset.n)));
      if ($("#stclr")) $("#stclr").onclick = () => setStars(0);
    };
    const setStars = async n => {
      await api(`/api/tours/${encodeURIComponent(t.id)}/rating`, post26({stars: n}));
      t.stars = n || null;
      drawStars();
    };
    drawStars();
  }
  /* ---- Sicherheitsnotiz ---- */
  if (safetySport(t.sport) && !$("#safety")) {
    const anchor = ($("#note") && $("#note").closest(".field")) || $("#profcard");
    if (anchor) {
      const s = await api(`/api/tours/${encodeURIComponent(t.id)}/safety`).catch(() => null);
      if (s && !$("#safety")) {
        anchor.insertAdjacentHTML(
          "afterend",
          `<details class="panel" id="safety" ${s.set ? "open" : ""} style="margin:0 0 18px"><summary><b>Sicherheit</b> <span class="mut">– Lawinenlage, Gruppe, Notfallausrüstung (nur Notiz)</span></summary>
           <div class="mut" style="margin:8px 0 2px">Lawinenwarnstufe (laut Lagebericht des Tages)</div>
           <div class="lvl" id="slvl">${[1, 2, 3, 4, 5].map(n => `<button type="button" data-l="${n}" style="${n <= 2 ? "color:#000;" : n > 3 ? "color:#000;" : ""}border-left:10px solid ${AVAL[n][0]}" title="${AVAL[n][1]}">${n} <small>${AVAL[n][1]}</small></button>`).join("")}</div>
           <div class="chips" id="sgear" style="margin:8px 0">${SAFE_GEAR.map(([k, l]) => `<label class="chip ${s.gear.includes(k) ? "on" : ""}" style="cursor:pointer"><input type="checkbox" value="${k}" ${s.gear.includes(k) ? "checked" : ""} style="display:none">${l}</label>`).join("")}</div>
           <label>Gruppe<input id="sgrp" maxlength="200" value="${esc(s.grp)}" placeholder="z. B. zu dritt: Anna, Ben, ich"></label>
           <label>Notiz<textarea id="snote" rows="2" maxlength="1000" placeholder="Schneedecke, Gefahrenstellen, Umkehrpunkt …">${esc(s.note)}</textarea></label>
           <div class="row"><button class="btn sm" id="ssave">Speichern</button><span id="smsg" class="mut"></span><span class="sp"></span><span class="mut" style="font-size:13px">Reine Dokumentation – ersetzt keinen Lawinenlagebericht.</span></div></details>`
        );
        rememberSize($("#snote"), "snote");
        let lvl = s.level;
        const mark = () => $("#slvl").querySelectorAll("button").forEach(b => b.classList.toggle("on", +b.dataset.l === lvl));
        mark();
        $("#slvl").onclick = e => {
          const b = e.target.closest("button");
          if (!b) return;
          lvl = lvl === +b.dataset.l ? null : +b.dataset.l;
          mark();
        };
        $("#sgear").querySelectorAll("input").forEach(i => (i.onchange = () => i.parentElement.classList.toggle("on", i.checked)));
        $("#ssave").onclick = async () => {
          try {
            await api(`/api/tours/${encodeURIComponent(t.id)}/safety`, post26({level: lvl, grp: $("#sgrp").value, note: $("#snote").value, gear: [...$("#sgear").querySelectorAll("input:checked")].map(i => i.value)}));
            $("#smsg").textContent = "gespeichert ✓";
          } catch (e) {
            $("#smsg").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
          }
        };
      }
    }
  }
  /* ---- Vergleich derselben Strecke (sobald die Wiederholungs-Auswertung da ist) ---- */
  const go = () => location.hash.includes(t.id) && showCompare(t);
  if (window.REPP) window.REPP.then(() => setTimeout(go, 0));
  else go();
};

function showCompare(t) {
  const r = REP[t.id];
  if (r && !$("#cmpseg") && $("#repnote")) {
    const L = [t, ...r.with.map(x => BY[x.id]).filter(Boolean)].sort((x, y) => x.start_ts - y.start_ts).filter(x => x.h > 0.05),
      best = L.reduce((m, x) => (x.h < m.h ? x : m), L[0] || t);
    if (L.length >= 2) {
      const mx = Math.max(...L.map(x => x.h)),
        rank = [...L].sort((x, y) => x.h - y.h).findIndex(x => x.id === t.id) + 1,
        hm = h => `${Math.floor(h)}:${pad2(Math.round((h % 1) * 60) % 60)} h`;
      $("#repnote").insertAdjacentHTML(
        "afterend",
        `<details id="cmpseg" class="panel" style="margin:0 0 14px"><summary><b>Vergleich dieser Strecke</b> <span class="mut">– diese Tour: ${rank}. schnellste von ${L.length}${best.id === t.id ? " 🏆" : ""}</span></summary>${L.map(
          x => `<div class="cmprow ${x.id === t.id ? "me" : ""}"><a href="#/tour/${x.id}">${dateS(x.date)}</a><div class="cmpbar"><i style="width:${(x.h / mx) * 100}%${x.id === best.id ? ";background:#d98a1f" : ""}"></i></div><span>${hm(x.h)} · ${nf(x.km / x.h, 1)} km/h${x.id === best.id ? " 🏆" : ""}</span></div>`
        ).join("")}<div class="mut" style="font-size:13px;margin-top:6px">Gesamtdauer inkl. Pausen. Bestzeit: ${dateS(best.date)} mit ${hm(best.h)}.</div></details>`
      );
    }
  }
}
