/* =====================  Prüfen / Aufräumen  ===================== */
VIEWS.check = async () => {
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Prüfen &amp; Aufräumen</h2><span class="sub" id="chs"></span></div><div id="chb" class="mut">Wird geprüft …</div>`;
  const r = await api("/api/check"),
    G = r.gaps,
    body = $("#chb");
  body.className = "";
  const nm = id =>
    BY[id] ? `<a href="#/tour/${id}">${esc(BY[id].name)}</a> <span class="mut">${fmtKm(BY[id].km)}</span>` : esc(id);
  body.innerHTML = `
   <div class="panel"><h2>Überblick</h2><div class="rows">
    <div class="r"><span>Touren insgesamt</span><b>${r.total}</b></div>
    <div class="r"><span>Mögliche Duplikate</span><b class="${r.duplicates.length ? "bad" : ""}">${r.duplicates.length}</b></div>
    <div class="r"><span>Auffälliger Aufstieg</span><b class="${r.suspicious.length ? "bad" : ""}">${r.suspicious.length}</b></div>
    <div class="r"><span>Noch mit Standardname</span><b>${r.default_names.length}</b></div>
    <div class="r"><span>Ohne gespeicherte Strecke / ohne Region / ohne Fotos</span><b>${G.no_route} / ${G.no_region} / ${G.no_photos}</b></div></div>
    <p class="mut fs13">Fehlende Strecken: Verwaltung → „Routen laden“. Fehlende Regionen: „Regionen bestimmen“.</p></div>
   <div class="panel gap"><h2>Mögliche Duplikate</h2>${r.duplicates.length ? `<div class="rows">${r.duplicates.map(d => `<div class="r db">${nm(d.a)}${d.a_local ? ` <button class="btn alt sm" data-del="${d.a}">lokal löschen</button>` : ""}<br>${nm(d.b)}${d.b_local ? ` <button class="btn alt sm" data-del="${d.b}">lokal löschen</button>` : ""}<small class="mut">${BY[d.a] ? fmtDatumKurz(BY[d.a].date) : ""} – gleiche Zeit, Startort und Länge</small></div>`).join("")}</div><p class="mut fs13">Lokale Touren (Zepp/GPX) lassen sich hier löschen, die Komoot-Tour nicht. Bei Komoot-Touren die Tour dort entfernen und „Komoot aktualisieren“ ausführen.</p>` : '<p class="ok">✓ Keine Duplikate gefunden.</p>'}</div>
   <div class="panel gap"><h2>Auffälliger Aufstieg</h2>${r.suspicious.length ? `<div class="row"><button class="btn" id="fixall">Alle ${r.suspicious.length} korrigieren</button><span id="fixm" class="mut"></span></div><div class="rows" id="fixl">${r.suspicious.map(t => `<div class="r" data-id="${t.id}"><span>${nm(t.id)}<small class="bad">${fmtHm(t.up_m)} Aufstieg auf ${fmtKm(t.km)}</small></span><button class="btn alt sm" data-fix="${t.id}">Korrigieren</button></div>`).join("")}</div>` : '<p class="ok">✓ Keine auffälligen Höhen.</p>'}</div>
   <div class="panel gap"><h2>Namen vergeben</h2>${
     r.default_names.length
       ? `<p class="mut">${r.default_names.length} Touren heißen noch wie vorgegeben. Mit „Vorschläge laden“ werden Namen aus Karte, Routen und Wanderführern vorbelegt; gespeichert wird erst mit „Speichern“.</p>
    <div class="row"><button class="btn" id="sugall">Vorschläge für die nächsten 10 laden</button><label class="chk m0"><input type="checkbox" id="rkomall"> auch bei Komoot umbenennen</label><span id="sugm" class="mut"></span></div>
    <div class="rows" id="nml">${r.default_names
      .map(
        t => `<div class="r nm" data-id="${t.id}" style="display:block"><div class="mut fs13">${fmtDatumKurz(BY[t.id]?.date || "0000-00-00")} · ${esc(sName(t.sport))} · ${t.km} km · <a href="#/tour/${t.id}">öffnen</a></div>
      <div class="row m4-0"><input class="nin fx1 mnw220" value="${esc(t.name)}"><button class="btn alt sm" data-sug="${t.id}">💡</button><button class="btn sm" data-save="${t.id}">Speichern</button></div><div class="chips sugs"></div></div>`
      )
      .join("")}</div>`
       : '<p class="ok">✓ Alle Touren haben einen eigenen Namen.</p>'
   }</div>`;
  {
    const SP = Object.keys(SPORT);                  // 3.59.0: alle Aktivitäten des Katalogs (01-grundlagen.js)
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
      `<div class="panel gap" id="impl"><h2>Unplausible Touren</h2>
      <p class="mut">Fehlaufzeichnungen (fast keine Strecke) und Touren, deren Tempo nicht zur Sportart passt. Sie zählen in Rekorden und Statistiken mit. Du kannst die Sportart ändern (bleibt auch nach dem Komoot-Abgleich) oder die Tour ausblenden (Daten bleiben erhalten, jederzeit wieder einblendbar).</p>
      ${
        im.length
          ? `<div class="rows">${im
              .map(
                t => `<div class="r" style="display:block" data-id="${esc(t.id)}" data-name="${esc(t.name)}" data-km="${t.km}" data-onk="${t.on_komoot ? 1 : ""}" data-local="${t.local ? 1 : ""}"><div class="iop cp" title="Tour öffnen"><a href="#/tour/${encodeURIComponent(t.id)}" class="fw600" style="text-decoration:underline">${esc(t.name)}</a> <span class="mut">${fmtDatumKurz(BY[t.id]?.date || "0000-00-00")} · ${esc(sName(t.sport))} · ${fmtKm(t.km)}</span></div>
        ${t.diag ? (t.diag.length ? `<div class="fs13 m2-0"><b>Mögliche Ursache:</b> ${t.diag.map(esc).join(" · ")} <span class="mut">– „🧹 Track korrigieren“ hilft dabei.</span></div>` : `<div class="mut fs13 m2-0">Der Track selbst ist unauffällig – wahrscheinlich ist nur die Sportart falsch.</div>`) : ""}
        <div class="row m4-0 g6"><span class="bad fs14">${esc(t.why)}</span><span class="sp"></span>
        <select class="isp">${SP.map(x => `<option value="${x}" ${x === (t.suggest || t.sport) ? "selected" : ""}>${esc(sName(x))}</option>`).join("")}</select><button class="btn alt sm" data-isp>Sportart ändern</button>${t.on_komoot ? `<label class="fs12 m0"><input type="checkbox" class="iko" checked> auch bei Komoot</label>` : ""}<button class="btn ${t.diag && t.diag.length ? "" : "alt "}sm" data-itf title="Ausreißer im Track entfernen, Seilbahn-/Autofahrten herausrechnen">🧹 Track korrigieren</button><button class="btn alt sm" data-ihide>Ausblenden</button><button class="btn alt sm" data-idel data-danger>Löschen …</button></div></div>`
              )
              .join("")}</div>`
          : '<p class="ok">✓ Keine auffälligen Touren.</p>'
      }
      ${hd.length ? `<h3 class="mt18">Ausgeblendet (${hd.length})</h3><div class="rows">${hd.map(t => `<div class="r" data-id="${esc(t.id)}"><span>${esc(t.name || t.id)} <span class="mut">${t.start_ts ? fmtDatumKurz(t.start_ts) : ""} · ${fmtKm((t.dist_m || 0) / 1000)}</span></span><button class="btn alt sm" data-ishow>Wieder einblenden</button><button class="btn alt sm" data-ishowfix title="Tour einblenden und gleich den GPS-Track korrigieren">Einblenden &amp; Track korrigieren</button></div>`).join("")}</div>` : ""}</div>`
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
            const m = uiModal(`<h3>Tour löschen?</h3><p>„${esc(d.name)}“ (${fmtKm(+d.km)}) wird aus Meine Touren entfernt – mit Strecke, Notizen und Tags. Zugeordnete Fotos bleiben erhalten.</p>
        ${d.onk ? `<label class="chk"><input type="checkbox" id="dk"> <b>auch bei Komoot endgültig löschen</b> <span class="mut">(lässt sich nicht rückgängig machen)</span></label>` : ""}
        ${!d.local && d.onk ? `<p class="mut fs13">Ohne Häkchen bleibt die Tour bei Komoot und wird beim nächsten Abgleich nicht wieder übernommen.</p>` : ""}
        <div id="dm" class="mut"></div><div class="uifoot"><button class="btn ghost" id="dx">Abbrechen</button><button class="btn alt uidanger" data-danger id="dok">Löschen</button></div>`);
            m.querySelector("#dx").onclick = () => m.remove();
            m.querySelector("#dok").onclick = async e => {
              const k = !!m.querySelector("#dk")?.checked;
              if (k && !await uiConfirm({text: `„${d.name}“ wirklich auch bei Komoot endgültig löschen?`, danger: true, ok: "Löschen"})) return;
              e.target.disabled = true;
              m.querySelector("#dm").textContent = "Wird gelöscht …";
              try {
                const r = await api(`/api/tours/${encodeURIComponent(d.id)}/delete`, {
                  method: "POST",
                  headers: {"content-type": "application/json"},
                  body: JSON.stringify({komoot: k}),
                });
                m.remove();
                if (r.komoot) uiAlert("Gelöscht – " + r.komoot + ".");
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
              if (r.komoot && !/geändert$/.test(r.komoot)) uiAlert(r.komoot);
              await after();
            } catch (e) {
              uiAlert(e.message);
              b.disabled = false;
            }
          })
      );
    $("#impl")
      .querySelectorAll("[data-itf]")
      .forEach(b => (b.onclick = () => trackFixDialog(b.closest("[data-id]").dataset.id, after)));
    $("#impl")
      .querySelectorAll("[data-ishowfix]")
      .forEach(
        b =>
          (b.onclick = async () => {
            const id = b.closest("[data-id]").dataset.id;
            b.disabled = true;
            try {
              await api(`/api/tours/${encodeURIComponent(id)}/hide`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({hide: false})});
              await loadTours();
              trackFixDialog(id, after);
            } catch (e) {
              uiAlert(e.message);
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
              uiAlert(e.message);
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
          `<span>${nm(id)}<small class="ok">korrigiert: ${fmtHm(x.up_m)} Aufstieg (vorher ${fmtHm(x.orig_up)})</small></span>`;
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
        if (!await uiConfirm({text: `Die lokale Tour „${BY[id]?.name || id}“ löschen? Die Komoot-Tour bleibt unberührt.`, danger: true, ok: "Löschen"})) return;
        try {
          await api(`/api/tours/${encodeURIComponent(id)}`, {method: "DELETE"});
          await loadTours();
          route();
        } catch (x) {
          uiAlert(x.message);
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
          uiAlert("Umbenennen fehlgeschlagen: " + e.message);
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

/* 3.50.0: Läufe der Zepp-Uhr, die noch „Wandern“ heißen. Sicher zuordenbare Touren hat der Umzug selbst umgestellt (app/sport_umzug.py); diese hier stammen von Komoot
   oder passen nur über Startzeit und Länge zu einem Lauf der Uhr – sie werden nicht geraten, sondern hier zur Wahl gestellt. Erscheint nur, wenn es solche Touren gibt. */
const _check350 = VIEWS.check;
VIEWS.check = async (...a) => {
  await _check350(...a);
  if (!$("#chb") || $("#zlauf")) return;
  let r;
  try {
    r = await api("/api/sport-umzug");
  } catch (e) {
    return;
  }
  const k = (r && r.kandidaten) || [],
    anker = $("#impl") || $("#chb .panel");
  if (!k.length || !anker || $("#zlauf")) return;
  anker.insertAdjacentHTML(
    "afterend",
    `<div class="panel gap" id="zlauf"><h2>Läufe von der Uhr</h2>
    <p class="mut">Laufen ist eine eigene Sportart. Diese Touren sind laut Zepp-Uhr ein Lauf, heißen hier aber noch „Wandern“. Sie stammen von Komoot oder passen nur über Startzeit und Länge zu einem Lauf der Uhr und wurden deshalb nicht von selbst umgestellt.</p>
    <div class="row"><button class="btn" id="zlall">Alle ${k.length} auf Laufen umstellen</button><span id="zlm" class="mut" role="status"></span></div>
    <div class="rows">${k
      .map(
        t =>
          `<div class="r" data-id="${esc(t.id)}"><span><a href="#/tour/${encodeURIComponent(t.id)}">${esc(t.name || t.id)}</a> <span class="mut">${fmtDatumKurz(t.start_ts)} · ${fmtKm(t.km)}${t.kmh ? " · " + fmtTempo(t.kmh) : ""}</span> · <span class="mut">${t.wie === "zeit" ? "passt über die Startzeit" : "Komoot-Tour"}</span></span><button class="btn alt sm" data-zl>Auf Laufen umstellen</button></div>`
      )
      .join("")}</div></div>`
  );
  const box = $("#zlauf"),
    go = async (ids, b) => {
      b.disabled = true;
      try {
        const x = await api("/api/sport-umzug/laufen", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids})});
        $("#zlm").textContent = x.n === 1 ? "1 Tour umgestellt." : `${x.n} Touren umgestellt.`;
        await loadTours();
        route();
      } catch (e) {
        uiAlert(e.message);
        b.disabled = false;
      }
    };
  box.querySelectorAll("[data-zl]").forEach(b => (b.onclick = () => go([b.closest("[data-id]").dataset.id], b)));
  $("#zlall").onclick = async e => {
    const b = e.currentTarget;
    if (!(await uiConfirm({text: `Alle ${k.length} Touren auf „Laufen“ umstellen? Die Sportart gilt dann als von dir gewählt und bleibt auch nach dem Komoot-Abgleich.`, ok: "Umstellen"}))) return;
    go(k.map(t => t.id), b);
  };
};

/* 3.59.0: Schneeschuh ist wieder eine eigene Sportart. Touren, die 3.50.0 zu „Wandern“ mit dem Schlagwort „Schneeschuh“ zusammengelegt hat, bleiben so, bis du sie hier
   „als Schneeschuh führst“ (nie von selbst). Das lässt sich zurücknehmen; das Schlagwort bleibt in beiden Fällen (app/sport_umzug.py). Erscheint nur, wenn es etwas zu tun gibt. */
const _check359 = VIEWS.check;
VIEWS.check = async (...a) => {
  await _check359(...a);
  if (!$("#chb") || $("#schnee")) return;
  let r;
  try {
    r = await api("/api/schneeschuh");
  } catch (e) {
    return;
  }
  const k = (r && r.kandidaten) || [], n = (r && r.umgestellt) || 0, anker = $("#zlauf") || $("#impl") || $("#chb .panel");
  if ((!k.length && !n) || !anker || $("#schnee")) return;
  anker.insertAdjacentHTML(
    "afterend",
    `<div class="panel gap" id="schnee"><h2>Schneeschuh-Touren</h2>
    <p class="mut"><span>Schneeschuh ist wieder eine eigene Sportart.</span> ${k.length ? `<span>${k.length === 1 ? "1 Tour heißt noch „Wandern“ und trägt das Schlagwort „Schneeschuh“." : `${k.length} Touren heißen noch „Wandern“ und tragen das Schlagwort „Schneeschuh“.`}</span> ` : ""}<span>Als Schneeschuh geführt, zählen sie in der Statistik als Schneeschuh und nicht mehr als Wandern; wer beides zusammen sehen will, legt in der Verwaltung eine Statistik-Gruppe an. Das Schlagwort bleibt.</span></p>
    <div class="row">${k.length ? `<button class="btn" id="snall">Schneeschuh-Touren als Schneeschuh führen (${k.length})</button>` : ""}${n ? `<button class="btn alt" id="snback">Zurücknehmen (${n})</button>` : ""}<span id="snm" class="mut" role="status"></span></div></div>`
  );
  const done = async (u, b, msg) => {
    b.disabled = true;
    try {
      const x = await api(u, {method: "POST", headers: {"content-type": "application/json"}, body: "{}"});
      $("#snm").textContent = msg(x.n);
      await loadTours();
      route();
    } catch (e) {
      uiAlert(e.message);
      b.disabled = false;
    }
  };
  if ($("#snall"))
    $("#snall").onclick = async e => {
      const b = e.currentTarget;
      if (!(await uiConfirm({text: `${k.length} Touren als „Schneeschuh“ führen? Das lässt sich hier wieder zurücknehmen.`, ok: "Als Schneeschuh führen"}))) return;
      done("/api/schneeschuh/umstellen", b, x => (x === 1 ? "1 Tour umgestellt." : `${x} Touren umgestellt.`));
    };
  if ($("#snback"))
    $("#snback").onclick = async e => {
      const b = e.currentTarget;
      if (!(await uiConfirm({text: "Die als Schneeschuh geführten Touren wieder als Wandern führen? Das Schlagwort „Schneeschuh“ bleibt.", ok: "Zurücknehmen"}))) return;
      done("/api/schneeschuh/zuruecknehmen", b, x => (x === 1 ? "1 Tour zurückgenommen." : `${x} Touren zurückgenommen.`));
    };
};
