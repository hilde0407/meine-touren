/* Einheitliche Dialoge statt confirm()/alert() (3.13.0).
   uiConfirm({title, text, ok, cancel, danger, html})  -> Promise<boolean>
   uiAlert({title, text, ok})                          -> Promise<void>
   Auch mit einem einfachen Text als Argument aufrufbar. Tastatur: Tab bleibt im Dialog, Esc = Abbrechen, Enter = Bestätigen (bei „danger“ nie von selbst:
   der Fokus startet dort auf „Abbrechen“). Der Hintergrund ist inert, der Fokus geht danach an den Auslöser zurück. Mehrere Aufrufe werden nacheinander gezeigt.
   Texte werden über die Übersetzungsschicht geleitet (TL) und als Text eingefügt (kein HTML, außer dem ausdrücklich gesetzten `html`, das der Aufrufer selbst escapen muss). */
(function () {
  const T = s => (typeof window.TL === "function" && typeof s === "string" ? window.TL(s) : s);
  const queue = [];
  let busy = false, seq = 0;

  const norm = (o, kind) => {
    o = o && typeof o === "object" && ("text" in o || "html" in o || "title" in o) ? Object.assign({}, o) : {text: o == null ? "" : String(o)};
    o.kind = kind;
    if (o.title == null) o.title = kind === "alert" ? "Hinweis" : o.danger ? "Bist du sicher?" : "Bitte bestätigen";
    if (o.ok == null) o.ok = "OK";
    if (o.cancel == null) o.cancel = "Abbrechen";
    return o;
  };

  function show(o, done) {
    const trigger = document.activeElement;
    const id = "uidlg" + ++seq;
    const host = document.createElement("div");
    host.className = "uidlg";
    const box = document.createElement("div");
    box.className = "uibox" + (o.danger ? " danger" : "");
    box.setAttribute("role", o.kind === "alert" || o.danger ? "alertdialog" : "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", id + "t");
    box.setAttribute("aria-describedby", id + "d");
    box.tabIndex = -1;
    const h = document.createElement("h2");
    h.id = id + "t";
    h.textContent = T(o.title);
    const p = document.createElement("div");
    p.id = id + "d";
    p.className = "uitext";
    if (o.html != null) p.innerHTML = o.html;
    else String(o.text ?? "").split("\n\n").forEach(part => {      // Absätze getrennt: jeder wird einzeln übersetzt
      const q = document.createElement("p");
      q.textContent = T(part);
      p.appendChild(q);
    });
    const foot = document.createElement("div");
    foot.className = "uifoot";
    const mk = (label, cls) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn " + cls;
      b.textContent = T(label);
      return b;
    };
    const bCancel = o.kind === "confirm" ? mk(o.cancel, "ghost") : null;
    const bOk = mk(o.ok, o.danger ? "alt uidanger" : "");
    if (o.danger) bOk.setAttribute("data-danger", "");
    if (bCancel) foot.appendChild(bCancel);
    foot.appendChild(bOk);
    box.append(h, p, foot);
    host.appendChild(box);

    const inerted = [];                                   // Hintergrund sperren (nur, was nicht schon gesperrt war)
    [...document.body.children].forEach(el => {
      if (!el.inert) { el.inert = true; inerted.push(el); }
    });
    document.body.appendChild(host);

    let closed = false;
    const close = val => {
      if (closed) return;
      closed = true;
      host.removeEventListener("keydown", key, true);
      host.remove();
      inerted.forEach(el => (el.inert = false));
      if (trigger && trigger.isConnected && typeof trigger.focus === "function") { try { trigger.focus(); } catch (e) {} }
      done(val);
    };
    const key = e => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(false); }
      else if (e.key === "Enter" && !o.danger && !(e.target instanceof HTMLButtonElement)) { e.preventDefault(); close(true); }
      else if (e.key === "Tab") {                         // Fokus-Falle
        const f = [...box.querySelectorAll("button")];
        const i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && (i === f.length - 1 || i < 0)) { e.preventDefault(); f[0].focus(); }
      }
    };
    host.addEventListener("keydown", key, true);
    bOk.onclick = () => close(true);
    if (bCancel) bCancel.onclick = () => close(false);
    host.addEventListener("mousedown", e => { if (e.target === host) close(false); });
    (o.danger && bCancel ? bCancel : bOk).focus();
  }

  function next() {
    if (busy || !queue.length) return;
    busy = true;
    const {o, res} = queue.shift();
    show(o, val => { busy = false; res(val); next(); });
  }
  const open = (o, kind) => new Promise(res => { queue.push({o: norm(o, kind), res: kind === "alert" ? () => res() : res}); next(); });

  window.uiConfirm = o => open(o, "confirm");
  window.uiAlert = o => open(o, "alert");
})();
