/* Einheitliche Dialoge statt confirm()/alert() (3.13.0).
   uiConfirm({title, text, ok, cancel, danger, html, onOpen(box, okButton)})  -> Promise<boolean>
   uiAlert({title, text, ok})                          -> Promise<void>   (Knopf „Schließen“; uiConfirm ohne ok: „Bestätigen“ – besser die Aktion nennen)
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
    if (o.ok == null) o.ok = kind === "alert" ? "Schließen" : "Bestätigen";        // 3.61.0: kein „OK“ – Aufrufer nennen die Hauptaktion selbst (Leitfaden 2.1)
    if (o.cancel == null) o.cancel = "Abbrechen";
    return o;
  };

  function show(o, done) {
    const trigger = document.activeElement;
    if (typeof window.closePanels === "function") window.closePanels();                // Karten-Panels schließen, nie ein Panel unter oder über einem Dialog
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
      else if (e.key === "Enter" && !o.danger && !(e.target instanceof HTMLButtonElement) && !/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) { e.preventDefault(); close(true); }
      else if (e.key === "Tab") {                         // Fokus-Falle
        const f = [...box.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])")];
        const i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && (i === f.length - 1 || i < 0)) { e.preventDefault(); f[0].focus(); }
      }
    };
    host.addEventListener("keydown", key, true);
    bOk.onclick = () => close(true);
    if (bCancel) bCancel.onclick = () => close(false);
    host.addEventListener("mousedown", e => { if (e.target === host) close(false); });
    if (typeof o.onOpen === "function") o.onOpen(box, bOk);   // 3.25.0: Dialog mit eigenen Bedienelementen (Auswahl lesen: auch nach dem Schließen am abgelösten Knoten)
    (o.danger && bCancel ? bCancel : bOk).focus();
  }

  function next() {
    if (busy || !queue.length) return;
    busy = true;
    const {o, res} = queue.shift();
    show(o, val => { busy = false; res(val); next(); });
  }
  const open = (o, kind) => new Promise(res => { queue.push({o: norm(o, kind), res: kind === "alert" ? () => res() : res}); next(); });


  /* 3.42.0 Formular-Fenster (früher .modal/.mbox): derselbe Rahmen wie uiConfirm, Hintergrund inert, Fokusfalle, Esc und Klick daneben schließen, Fokus geht an den Auslöser zurück.
     uiModal(html) -> Host-Element (class "uidlg uimod"); darin .uibox mit dem übergebenen HTML. `host.remove()` schließt sauber (stellt Hintergrund und Fokus wieder her);
     eine erste Überschrift (h2/h3) wird zur Titelzeile des Dialogs. */
  let mseq = 0;
  window.uiModal = html => {
    const trigger = document.activeElement, id = "uimd" + ++mseq;
    if (typeof window.closePanels === "function") window.closePanels();
    const host = document.createElement("div");
    host.className = "uidlg uimod";
    const box = document.createElement("div");
    box.className = "uibox";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.tabIndex = -1;
    box.innerHTML = html;
    let h = box.querySelector(":scope > h2, :scope > h3, :scope > .sec h2");
    if (h && h.tagName === "H3") {
      const h2 = document.createElement("h2");
      h2.innerHTML = h.innerHTML;
      for (const a of h.attributes) h2.setAttribute(a.name, a.value);
      h.replaceWith(h2);
      h = h2;
    }
    if (h) { if (!h.id) h.id = id; box.setAttribute("aria-labelledby", h.id); }
    host.appendChild(box);
    const inerted = [];
    [...document.body.children].forEach(el => { if (!el.inert) { el.inert = true; inerted.push(el); } });
    document.body.appendChild(host);
    const realRemove = Element.prototype.remove;
    let closed = false;
    const close = () => {
      if (closed) return;
      closed = true;
      host.removeEventListener("keydown", key, true);
      realRemove.call(host);
      inerted.forEach(el => (el.inert = false));
      if (typeof host.onClose === "function") host.onClose();    // 3.46.0: Aufräumen des Aufrufers (vor der Rückgabe des Fokus)
      if (trigger && trigger.isConnected && typeof trigger.focus === "function") { try { trigger.focus(); } catch (e) {} }
    };
    const key = e => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (!(host.noClose && host.noClose())) close(); }
      else if (e.key === "Tab") {
        const f = [...box.querySelectorAll("button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), a[href], summary")].filter(x => x.offsetParent !== null);
        if (!f.length) { e.preventDefault(); box.focus(); return; }
        const i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && (i === f.length - 1 || i < 0)) { e.preventDefault(); f[0].focus(); }
      }
    };
    host.addEventListener("keydown", key, true);
    host.addEventListener("mousedown", e => { if (e.target === host && !(host.noClose && host.noClose())) close(); });   // host.noClose(): z. B. solange ein Import läuft
    host.remove = close;
    host._close = close;
    box.focus({preventScroll: true});
    return host;
  };

  window.uiConfirm = o => open(o, "confirm");
  window.uiAlert = o => open(o, "alert");

  /* 3.61.0 Eingabe statt prompt() (Leitfaden 2.1: keine Browser-Fenster): ein Feld, „Abbrechen“ links, die benannte Hauptaktion rechts; Enter im Feld bestätigt.
       uiPrompt({title, label, value, type, ok, hint, min}) -> Promise<string|null>   (null = abgebrochen; min = Mindestlänge, sonst bleibt der Knopf aus) */
  window.uiPrompt = p => {
    p = Object.assign({title: "Eingabe", label: "", value: "", type: "text", ok: "Speichern", hint: "", min: 0}, p || {});
    let inp = null;
    const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
    const html = `<label class="uiplbl">${esc(T(p.label))}<input class="uipin" type="${p.type === "password" ? "password" : p.type === "email" ? "email" : "text"}" value="${esc(p.value)}" autocomplete="${p.type === "password" ? "new-password" : "off"}"></label>${p.hint ? `<p class="mut fs13">${esc(T(p.hint))}</p>` : ""}`;
    return open({title: p.title, html, ok: p.ok, onOpen: (box, bOk) => {
      inp = box.querySelector(".uipin");
      const chk = () => (bOk.disabled = inp.value.length < (p.min || 0));
      inp.addEventListener("input", chk);
      inp.addEventListener("keydown", e => { if (e.key === "Enter" && !bOk.disabled) { e.preventDefault(); bOk.click(); } });
      chk();
      setTimeout(() => { inp.focus(); inp.select(); }, 0);
    }}, "confirm").then(ok => (ok && inp ? inp.value : null));
  };
  /* Link zeigen, wenn das Kopieren in die Zwischenablage nicht geht (statt prompt("Link …", url)): Feld zum Markieren, Knopf „Schließen“ */
  window.uiLink = (title, url) => open({title, html: `<input class="uipin" readonly value="${String(url).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c])}">`, ok: "Schließen",
    onOpen: box => setTimeout(() => { const i = box.querySelector(".uipin"); i.focus(); i.select(); }, 0)}, "alert");
})();
