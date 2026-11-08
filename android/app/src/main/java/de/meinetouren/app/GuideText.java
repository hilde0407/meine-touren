package de.meinetouren.app;

import java.util.Locale;

/** Texte der Sprachansagen in Deutsch, Englisch, Französisch und Spanisch (reine Logik, ohne Android-Bezug). */
public final class GuideText {
    private GuideText() { }

    /** Aktuelle Ansagesprache: "de", "en", "fr" oder "es". */
    public static volatile String lang = "de";

    public static String norm(String l) {
        if (l == null) return "en";
        l = l.toLowerCase(Locale.ROOT);
        if (l.length() > 2) l = l.substring(0, 2);
        return l.equals("de") || l.equals("en") || l.equals("fr") || l.equals("es") ? l : "en";
    }

    public static Locale locale() {
        switch (lang) {
            case "en": return Locale.UK;
            case "fr": return Locale.FRANCE;
            case "es": return new Locale("es", "ES");
            default: return Locale.GERMANY;
        }
    }

    private static int i() { switch (lang) { case "en": return 1; case "fr": return 2; case "es": return 3; default: return 0; } }
    private static String t(String de, String en, String fr, String es) { return new String[]{de, en, fr, es}[i()]; }

    private static String num(double v) { return String.format(locale(), "%.1f", v); }

    /** Entfernung nach „in …“ („in 100 Metern“). */
    public static String dist(double m) {
        if (m >= 950) {
            double km = Math.round(m / 100.0) / 10.0;
            String s = km == Math.rint(km) ? String.valueOf((long) km) : num(km);
            return s + t(" Kilometer", km == 1 ? " kilometre" : " kilometres", km == 1 ? " kilomètre" : " kilomètres", km == 1 ? " kilómetro" : " kilómetros");
        }
        long r = m < 100 ? Math.max(10, Math.round(m / 10.0) * 10) : Math.round(m / 50.0) * 50;
        return r + t(" Metern", " metres", " mètres", " metros");
    }

    /** Entfernung als Satzglied im Nominativ („… ist 200 Meter entfernt“). */
    public static String distNom(double m) {
        return lang.equals("de") ? dist(m).replace("Metern", "Meter") : dist(m);
    }

    public static String instruction(double angle) {
        double a = Math.abs(angle);
        boolean right = angle > 0;
        if (a >= 150) return t("Kehre nach " + (right ? "rechts" : "links"), "make a U-turn to the " + (right ? "right" : "left"),
                "faites demi-tour par la " + (right ? "droite" : "gauche"), "da la vuelta por la " + (right ? "derecha" : "izquierda"));
        if (a >= 120) return t("scharf " + (right ? "rechts" : "links") + " abbiegen", "turn sharp " + (right ? "right" : "left"),
                "tournez franchement à " + (right ? "droite" : "gauche"), "gira cerrado a la " + (right ? "derecha" : "izquierda"));
        if (a >= 65) return t((right ? "rechts" : "links") + " abbiegen", "turn " + (right ? "right" : "left"),
                "tournez à " + (right ? "droite" : "gauche"), "gira a la " + (right ? "derecha" : "izquierda"));
        return t("leicht " + (right ? "rechts" : "links") + " halten", "bear " + (right ? "right" : "left"),
                "serrez légèrement à " + (right ? "droite" : "gauche"), "mantente ligeramente a la " + (right ? "derecha" : "izquierda"));
    }

    private static String cap(String s) { return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1); }

    public static String onRoute() { return t("Du bist auf der Route.", "You are on the route.", "Vous êtes sur l’itinéraire.", "Estás en la ruta."); }
    public static String onRouteLen(double m) {
        return t("Du bist auf der Route. Sie ist " + distNom(m) + " lang.", "You are on the route. It is " + dist(m) + " long.",
                "Vous êtes sur l’itinéraire. Il fait " + dist(m) + ".", "Estás en la ruta. Tiene " + dist(m) + " de largo.");
    }
    public static String routeAway(double m) {
        return t("Die Route ist " + distNom(m) + " entfernt. Geh zur Route, dann beginnt die Führung.",
                "The route is " + dist(m) + " away. Walk to the route and the guidance will begin.",
                "L’itinéraire est à " + dist(m) + ". Rejoignez-le et le guidage commencera.",
                "La ruta está a " + dist(m) + ". Ve hasta la ruta y comenzará la guía.");
    }
    public static String offRoute(double m) {
        return t("Du bist vom Weg abgekommen. Bis zur Route sind es " + distNom(m) + ".", "You have left the route. The route is " + dist(m) + " away.",
                "Vous avez quitté l’itinéraire. Il est à " + dist(m) + ".", "Te has salido de la ruta. La ruta está a " + dist(m) + ".");
    }
    public static String stillOff(double m) {
        return t("Noch nicht auf der Route, " + distNom(m) + " entfernt.", "Still not on the route, " + dist(m) + " away.",
                "Toujours pas sur l’itinéraire, à " + dist(m) + ".", "Aún no estás en la ruta, a " + dist(m) + ".");
    }
    public static String backOn() { return t("Wieder auf dem Weg.", "Back on track.", "De nouveau sur le bon chemin.", "De nuevo en el camino."); }
    public static String thenPart(double angle) { return t(", danach ", ", then ", ", puis ", ", después ") + instruction(angle); }
    public static String now(double angle, String then) {
        return cap(t("jetzt ", "now ", "maintenant ", "ahora ") + instruction(angle)) + then + ".";
    }
    public static String ahead(double d, double angle, String then) {
        return t("In " + dist(d) + " ", "In " + dist(d) + ", ", "Dans " + dist(d) + ", ", "En " + dist(d) + " ") + instruction(angle) + then + ".";
    }
    public static String oneKm() { return t("Noch ein Kilometer bis zum Ziel.", "One kilometre to go.", "Encore un kilomètre jusqu’à l’arrivée.", "Queda un kilómetro hasta el destino."); }
    public static String arrived() { return t("Du hast das Ziel erreicht.", "You have reached your destination.", "Vous êtes arrivé à destination.", "Has llegado a tu destino."); }
    public static String test() {
        return t("Die Sprachansagen sind eingeschaltet. In 100 Metern links abbiegen.", "Voice guidance is on. In 100 metres, turn left.",
                "Le guidage vocal est activé. Dans 100 mètres, tournez à gauche.", "La guía por voz está activada. En 100 metros, gira a la izquierda.");
    }
}
