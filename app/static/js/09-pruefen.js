/* =====================  Prüfen / Aufräumen  ===================== */
VIEWS.check = async () => {
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Prüfen &amp; Aufräumen</h2><span class="sub" id="chs"></span></div><div id="chb" class="mut">Wird geprüft …</div>`;
  const r = await api("/api/check"),
    G = r.gaps,
    body = $("#chb");
  body.className = "";
  const nm = id =>
    BY[id] ? `<a href="#/tour/${id}">${esc(BY[id].name)}</a> <span class="mut">${BY[id].km.toFixed(1)} km</span>` : esc(id);
  body.innerHTML = `
   <div class="panel"><h2>Überblick</h2><div class="rows">
    <div class="r"><span>Touren insgesamt</span><b>${r.total}</b></div>
    <div class="r"><span>Mögliche Duplikate</span><b class="${r.duplicates.length ? "bad" : ""}">${r.duplicates.length}</b></div>
    <div class="r"><span>Auffällige Höhenmeter</span><b class="${r.suspicious.length ? "bad" : ""}">${r.suspicious.length}</b></div>
    <div class="r"><span>Noch mit Standardname</span><b>${r.default_names.length}</b></div>
    <div class="r"><span>Ohne gespeicherte Strecke / ohne Region / ohne Fotos</span><b>${G.no_route} / ${G.no_region} / ${G.no_photos}</b></div></div>
    <p class="mut" style="font-size:13px">Fehlende Strecken: Verwaltung → „Routen laden“. Fehlende Regionen: „Regionen bestimmen“.</p></div>
   <div class="panel" style="margin-top:22px"><h2>Mögliche Duplikate</h2>${r.duplicates.length ? `<div class="rows">${r.duplicates.map(d => `<div class="r" style="display:block">${nm(d.a)}${d.a_local ? ` <button class="btn alt sm" data-del="${d.a}">lokal löschen</button>` : ""}<br>${nm(d.b)}${d.b_local ? ` <button class="btn alt sm" data-del="${d.b}">lokal löschen</button>` : ""}<small class="mut">${BY[d.a] ? dateS(BY[d.a].date) : ""} – gleiche Zeit, Startort und Länge</small></div>`).join("")}</div><p class="mut" style="font-size:13px">Lokale Touren (Zepp/GPX) lassen sich hier löschen, die Komoot-Tour nicht. Bei Komoot-Touren die Tour dort entfernen und „Komoot aktualisieren“ ausführen.</p>` : '<p class="ok">✓ Keine Duplikate gefunden.</p>'}</div>
   <div class="panel" style="margin-top:22px"><h2>Auffällige Höhenmeter</h2>${r.suspicious.length ? `<div class="row"><button class="btn" id="fixall">Alle ${r.suspicious.length} korrigieren</button><span id="fixm" class="mut"></span></div><div class="rows" id="fixl">${r.suspicious.map(t => `<div class="r" data-id="${t.id}"><span>${nm(t.id)}<small class="bad">${nf(t.up_m, 0)} m Aufstieg auf ${nf(t.km, 1)} km</small></span><button class="btn alt sm" data-fix="${t.id}">Korrigieren</button></div>`).join("")}</div>` : '<p class="ok">✓ Keine auffälligen Höhen.</p>'}</div>
   <div class="panel" style="margin-top:22px"><h2>Namen vergeben</h2>${
     r.default_names.length
       ? `<p class="mut">${r.default_names.length} Touren heißen noch wie vorgegeben. Mit „Vorschläge laden“ werden Namen aus Karte, Routen und Wanderführern vorbelegt; gespeichert wird erst mit „Speichern“.</p>
    <div class="row"><button class="btn" id="sugall">Vorschläge für die nächsten 10 laden</button><label class="chk" style="margin:0"><input type="checkbox" id="rkomall"> auch bei Komoot umbenennen</label><span id="sugm" class="mut"></span></div>
    <div class="rows" id="nml">${r.default_names
      .map(
        t => `<div class="r nm" data-id="${t.id}" style="display:block"><div class="mut" style="font-size:13px">${dateS(BY[t.id]?.date || "0000-00-00")} · ${esc(sName(t.sport))} · ${t.km} km · <a href="#/tour/${t.id}">öffnen</a></div>
      <div class="row" style="margin:4px 0"><input class="nin" value="${esc(t.name)}" style="flex:1;min-width:220px"><button class="btn alt sm" data-sug="${t.id}">💡</button><button class="btn sm" data-save="${t.id}">Speichern</button></div><div class="chips sugs"></div></div>`
      )
      .join("")}</div>`
       : '<p class="ok">✓ Alle Touren haben einen eigenen Namen.</p>'
   }</div>`;
  {
    const SP = [
      "hike",
      "touringbicycle",
      "e_touringbicycle",
      "racebike",
      "mtb",
      "jogging",
      "skialpin",
      "snowshoe",
      "mountaineering",
      "nordic",
      "nordicwalking",
      "skitour",
    ];
    const im = r.implausible || [],
      hd = r.hidden || [];
    const first = body.querySelector(".panel");
    first
      .querySelector(".rows")
      .insertAdjacentHTML(
        "beforeend",
        `<div class="r"><span>Unplausible Touren</span><b class="${im.length ? "bad" : ""}">${im.length}</b></div>`
      );
    first.insertAdjacentHTML(
      "afterend",
      `<div class="panel" style="margin-top:22px" id="impl"><h2>Unplausible Touren</h2>
      <p class="mut">Fehlaufzeichnungen (fast keine Strecke) und Touren, deren Tempo nicht zur Sportart passt. Sie zählen in Rekorden und Statistiken mit. Du kannst die Sportart ändern (bleibt auch nach dem Komoot-Abgleich) oder die Tour ausblenden (Daten bleiben erhalten, jederzeit wieder einblendbar).</p>
      ${
        im.length
          ? `<div class="rows">${im
              .map(
                t => `<div class="r" style="display:block" data-id="${esc(t.id)}" data-name="${esc(t.name)}" data-km="${t.km}" data-onk="${t.on_komoot ? 1 : ""}" data-local="${t.local ? 1 : ""}"><div class="iop" style="cursor:pointer" title="Tour öffnen"><a href="#/tour/${encodeURIComponent(t.id)}" style="text-decoration:underline;font-weight:600">${esc(t.name)}</a> <span class="mut">${dateS(BY[t.id]?.date || "0000-00-00")} · ${esc(sName(t.sport))} · ${nf(t.km, 2)} km</span></div>
        <div class="row" style="margin:4px 0;gap:6px"><span class="bad" style="font-size:14px">${esc(t.why)}</span><span class="sp"></span>
        <select class="isp">${SP.map(x => `<option value="${x}" ${x === (t.suggest || t.sport) ? "selected" : ""}>${esc(sName(x))}</option>`).join("")}</select><button class="btn alt sm" data-isp>Sportart ändern</button>${t.on_komoot ? `<label style="font-size:12px;margin:0"><input type="checkbox" class="iko" checked> auch bei Komoot</label>` : ""}<button class="btn alt sm" data-ihide>Ausblenden</button><button class="btn alt sm" data-idel style="color:var(--bad,#b3261e)">Löschen …</button></div></div>`
              )
              .join("")}</div>`
          : '<p class="ok">✓ Keine auffälligen Touren.</p>'
      }
      ${hd.length ? `<h3 style="margin-top:18px">Ausgeblendet (${hd.length})</h3><div class="rows">${hd.map(t => `<div class="r" data-id="${esc(t.id)}"><span>${esc(t.name || t.id)} <span class="mut">${t.start_ts ? new Date(t.start_ts * 1000).toLocaleDateString("de-DE") : ""} · ${nf((t.dist_m || 0) / 1000, 2)} km</span></span><button class="btn alt sm" data-ishow>Wieder einblenden</button></div>`).join("")}</div>` : ""}</div>`
    );
    const after = async () => {
      await loadTours();
      route();
    };
    $("#impl")
      .querySelectorAll(".iop")
      .forEach(
        d =>
          (d.onclick = e => {
            if (e.target.tagName !== "A") location.hash = "#/tour/" + encodeURIComponent(d.closest("[data-id]").dataset.id);
          })
      );
    $("#impl")
      .querySelectorAll("[data-idel]")
      .forEach(
        b =>
          (b.onclick = () => {
            const row = b.closest("[data-id]"),
              d = row.dataset;
            const m = document.createElement("div");
            m.className = "modal";
            m.innerHTML = `<div class="mbox"><h3>Tour löschen?</h3><p>„${esc(d.name)}“ (${nf(+d.km, 2)} km) wird aus Meine Touren entfernt – mit Strecke, Notizen und Tags. Zugeordnete Fotos bleiben erhalten.</p>
        ${d.onk ? `<label class="chk"><input type="checkbox" id="dk"> <b>auch bei Komoot endgültig löschen</b> <span class="mut">(lässt sich nicht rückgängig machen)</span></label>` : ""}
        ${!d.local && d.onk ? `<p class="mut" style="font-size:13px">Ohne Häkchen bleibt die Tour bei Komoot und wird beim nächsten Abgleich nicht wieder übernommen.</p>` : ""}
        <div id="dm" class="mut"></div><div style="margin-top:18px;display:flex;gap:8px;justify-content:flex-end"><button class="btn alt" id="dx">Abbrechen</button><button class="btn" id="dok" style="background:var(--bad,#b3261e);border-color:var(--bad,#b3261e);color:#fff">Löschen</button></div></div>`;
            document.body.appendChild(m);
            m.querySelector("#dx").onclick = () => m.remove();
            m.onclick = e => {
              if (e.target === m) m.remove();
            };
            m.querySelector("#dok").onclick = async e => {
              const k = !!m.querySelector("#dk")?.checked;
              if (k && !confirm(`„${d.name}“ wirklich auch bei Komoot endgültig löschen?`)) return;
              e.target.disabled = true;
              m.querySelector("#dm").textContent = "Wird gelöscht …";
              try {
                const r = await api(`/api/tours/${encodeURIComponent(d.id)}/delete`, {
                  method: "POST",
                  headers: {"content-type": "application/json"},
                  body: JSON.stringify({komoot: k}),
                });
                m.remove();
                if (r.komoot) alert("Gelöscht – " + r.komoot + ".");
                await after();
              } catch (x) {
                m.querySelector("#dm").innerHTML = `<span class="bad">${esc(x.message)}</span>`;
                e.target.disabled = false;
              }
            };
          })
      );
    $("#impl")
      .querySelectorAll("[data-isp]")
      .forEach(
        b =>
          (b.onclick = async () => {
            const row = b.closest("[data-id]");
            b.disabled = true;
            try {
              const r = await api(`/api/tours/${encodeURIComponent(row.dataset.id)}/sport`, {
                method: "POST",
                headers: {"content-type": "application/json"},
                body: JSON.stringify({sport: row.querySelector(".isp").value, komoot: !!row.querySelector(".iko")?.checked}),
              });
              if (r.komoot && !/geändert$/.test(r.komoot)) alert(r.komoot);
              await after();
            } catch (e) {
              alert(e.message);
              b.disabled = false;
            }
          })
      );
    $("#impl")
      .querySelectorAll("[data-ihide],[data-ishow]")
      .forEach(
        b =>
          (b.onclick = async () => {
            const row = b.closest("[data-id]");
            b.disabled = true;
            try {
              await api(`/api/tours/${encodeURIComponent(row.dataset.id)}/hide`, {
                method: "POST",
                headers: {"content-type": "application/json"},
                body: JSON.stringify({hide: b.hasAttribute("data-ihide")}),
              });
              await after();
            } catch (e) {
              alert(e.message);
              b.disabled = false;
            }
          })
      );
  }
  const fix1 = async id => {
    const b = body.querySelector(`[data-fix="${id}"]`);
    if (b) {
      b.disabled = true;
      b.textContent = "…";
    }
    try {
      const x = await api(`/api/tours/${encodeURIComponent(id)}/elev-fix`, {method: "POST"});
      if (b)
        b.closest(".r").innerHTML =
          `<span>${nm(id)}<small class="ok">korrigiert: ${nf(x.up_m, 0)} m Aufstieg (vorher ${nf(x.orig_up, 0)} m)</small></span>`;
      return true;
    } catch (e) {
      if (b) {
        b.disabled = false;
        b.textContent = "Fehler – nochmal";
        b.title = e.message;
      }
      return false;
    }
  };
  body.querySelectorAll("[data-fix]").forEach(
    b =>
      (b.onclick = async () => {
        await fix1(b.dataset.fix);
        loadTours();
      })
  );
  body.querySelectorAll("[data-del]").forEach(
    b =>
      (b.onclick = async () => {
        const id = b.dataset.del;
        if (!confirm(`Die lokale Tour „${BY[id]?.name || id}“ löschen? Die Komoot-Tour bleibt unberührt.`)) return;
        try {
          await api(`/api/tours/${encodeURIComponent(id)}`, {method: "DELETE"});
          await loadTours();
          route();
        } catch (x) {
          alert(x.message);
        }
      })
  );
  if ($("#fixall"))
    $("#fixall").onclick = async e => {
      e.target.disabled = true;
      let n = 0;
      for (const t of r.suspicious) {
        $("#fixm").textContent = `Korrigiere ${++n}/${r.suspicious.length} …`;
        await fix1(t.id);
      }
      $("#fixm").textContent = "Fertig.";
      await loadTours();
    };
  const sug = async row => {
    const id = row.dataset.id,
      box = row.querySelector(".sugs"),
      inp = row.querySelector(".nin");
    box.innerHTML = '<span class="mut">Suche …</span>';
    try {
      const s = (await api(`/api/tours/${encodeURIComponent(id)}/name-suggestions?part=all`)).suggestions;
      box.innerHTML = "";
      if (!s.length) {
        box.innerHTML = '<span class="mut">Keine Vorschläge.</span>';
        return;
      }
      if (DEFAULT_RX.test(inp.value)) inp.value = s[0];
      s.forEach(x => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "btn alt sm";
        b.textContent = x;
        b.onclick = () => {
          inp.value = x;
        };
        box.appendChild(b);
      });
    } catch (e) {
      box.innerHTML = `<span class="mut">Keine Vorschläge (${esc(e.message)})</span>`;
    }
  };
  const DEFAULT_RX = /\d{2}\.\d{2}\.\d{4}/;
  body.querySelectorAll("[data-sug]").forEach(b => (b.onclick = () => sug(b.closest(".nm"))));
  body.querySelectorAll("[data-save]").forEach(
    b =>
      (b.onclick = async () => {
        const row = b.closest(".nm"),
          nn = row.querySelector(".nin").value.trim();
        if (!nn) return;
        b.disabled = true;
        try {
          const x = await api(`/api/tours/${encodeURIComponent(b.dataset.save)}/rename`, {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({name: nn, komoot: $("#rkomall").checked}),
          });
          row.innerHTML = `<span class="ok">✓ ${esc(nn)}</span>${$("#rkomall").checked && !x.komoot ? ` <span class="bad">(bei Komoot nicht geklappt: ${esc(x.warning || "")})</span>` : ""}`;
          if (BY[b.dataset.save]) BY[b.dataset.save].name = nn;
        } catch (e) {
          b.disabled = false;
          alert("Umbenennen fehlgeschlagen: " + e.message);
        }
      })
  );
  if ($("#sugall"))
    $("#sugall").onclick = async e => {
      e.target.disabled = true;
      const rows = [...body.querySelectorAll(".nm")].filter(x => !x.querySelector(".sugs").children.length).slice(0, 10);
      let n = 0;
      const q = rows.slice(),
        done = () => {
          $("#sugm").textContent = `Lade ${n}/${rows.length} …`;
        };
      done();
      await Promise.all(
        [0, 1, 2].map(async () => {
          while (q.length) {
            await sug(q.shift());
            n++;
            done();
          }
        })
      ); // 3 Touren gleichzeitig: Wartezeiten der Dienste überlappen
      $("#sugm").textContent = rows.length ? "Fertig – bitte prüfen und speichern." : "Alle schon geladen.";
      e.target.disabled = false;
    };
};
