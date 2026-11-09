/* Service-Worker anmelden (eigene Datei statt Inline-Skript, wegen der Content-Security-Policy) */
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) navigator.serviceWorker.register("sw.js").catch(() => {});
