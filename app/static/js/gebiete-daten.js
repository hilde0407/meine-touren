/* Gebiete (3.62.1): eingebaute Gebietstabelle (Gebirge, Täler, Inseln, Küsten, Landschaften) und die Zuordnung einer Tour zu Gebieten.
   Läuft im Browser (globales `Gebiete`) und in Node (tests/test_gebiete_362.py, tests/gebiete_pruefen.js).

   WICHTIG – ALLE GRENZEN SIND NÄHERUNGEN. Ein Gebiet besteht aus einem oder mehreren Rechtecken (boxen) bzw. einfachen Vielecken (poly); sie sind aus der
   Erinnerung an Ortslagen und Gipfel gezogen, nicht aus amtlichen Grenzen. An den Rändern kann eine Tour dem Nachbargebiet zugeordnet werden oder keinem.
   Gedacht ist die Zuordnung nur für Suche und Anzeige („Gomera“, „Lungau“, „Zillertal“ finden), nicht für Statistik oder Grenzfragen.
   Es gibt keine Datenbank, kein Netz: die Zuordnung wird im Browser aus den Startkoordinaten (t.lat, t.lng) berechnet. Der Bezirk (g_county) ist nur dort
   eine zusätzliche Möglichkeit, wo er sicher passt (Lungau = Bezirk Tamsweg, Südtirol = Provinz Bozen); fehlt er (Touren ab 2026), gilt allein die Koordinate.

   Aufbau eines Gebiets (Funktion g(id, name, typ, eltern, boxen, opt)):
     id      eindeutige Kennung (klein, ohne Leerzeichen)
     name    Anzeigename (deutsch oder Originalname)
     typ     "gebirge" | "tal" | "insel" | "kueste" | "region"
     eltern  Kennung des übergeordneten Gebiets oder null. Eltern werden jeder Tour mit zugerechnet (Insel + Archipel, Südschwarzwald + Schwarzwald).
             Gebiete ohne Rechtecke und ohne Bezirke (reine Oberbegriffe, z. B. „Alpen“, „Kanaren“) gelten nur über ihre Kinder.
     boxen   [[lat0, lng0, lat1, lng1], …] Rechtecke (Süd, West, Nord, Ost), mehrere je Gebiet erlaubt
     opt.poly    [[[lat, lng], …], …] einfache Vielecke (zusätzlich zu den Rechtecken)
     opt.alias   weitere Suchwörter (deutsch, Landessprache, englisch)
     opt.county  Bezirke/Landkreise (g_county), die das Gebiet sicher beschreiben („Bezirk“, „Landkreis“, „Provinz“ am Anfang zählt nicht)
     opt.nicht   Ausschluss: Rechtecke [lat0, lng0, lat1, lng1] oder die Kennung eines anderen Gebiets (dessen Fläche, es sei denn, dessen nichtKreis nennt den Bezirk der Tour)
     opt.nichtKreis  Bezirke/Landkreise (g_county), in denen das Gebiet nie liegt (3.68.0): trifft sonst die Koordinate, zählt die Tour trotzdem nicht (z. B. Südtirol nie in „Bezirk Lienz“ oder „Provinz Trient“)
     opt.in      zusätzlich muss die Koordinate auch in der Fläche dieses Gebiets liegen (Unterteilung eines Vielecks durch Rechtecke)
     opt.prio    Gleichstand bei der Anzeige: höhere Zahl gewinnt
     opt.anz     true: auch ein Gebiet vom Typ „region“ darf in der Regionszeile erscheinen (sonst nur Gebirge, Täler, Inseln, Küsten)

   Anzeige: das spezifischste Gebiet (am tiefsten in der Eltern-Kette, bei Gleichstand das kleinere) – nur eines, ohne Doppelungen mit Ort, Bundesland, Land. */
const Gebiete = (() => {
  const GEB = "gebirge", TAL = "tal", INS = "insel", KUE = "kueste", REG = "region";
  const L = [];
  const g = (id, name, typ, eltern, boxen, o = {}) => {
    L.push({id, name, typ, eltern: eltern || null, boxen: boxen || [], poly: o.poly || [], alias: o.alias || [], county: o.county || [], nicht: o.nicht || [], nichtKreis: o.nichtKreis || [], in: o.in || null, prio: o.prio || 0, anz: o.anz === true});
  };

  /* ===================== Alpen: Österreich ===================== */
  g("alpen", "Alpen", GEB, null, [], {alias: ["Alps", "Alpes", "Alpi"]});
  g("lungau", "Lungau", REG, "alpen", [[47.02, 13.45, 47.22, 14.02]], {alias: ["Bezirk Tamsweg", "Tamsweg"], county: ["Tamsweg"], anz: true});
  g("pongau", "Pongau", REG, "alpen", [[47.10, 13.08, 47.50, 13.52]], {alias: ["Gastein"], county: ["St. Johann im Pongau", "Sankt Johann im Pongau"], anz: true});
  g("pinzgau", "Pinzgau", REG, "alpen", [[47.12, 12.15, 47.62, 13.08]], {alias: ["Zell am See", "Kaprun"], county: ["Zell am See"], nicht: [[47.38, 12.0, 47.70, 12.62], [47.02, 13.03, 47.24, 13.08]], anz: true});   // 3.70.1: Gasteinertal (Bad Hofgastein, Heißingfelding) liegt im Pongau, nicht im Pinzgau; Rauris (13.00 E) bleibt Pinzgau
  g("tennengau", "Tennengau", REG, "alpen", [[47.50, 13.08, 47.75, 13.45]], {county: ["Hallein"], anz: true});
  g("salzkammergut", "Salzkammergut", REG, "alpen", [[47.52, 13.30, 48.00, 14.00]], {alias: ["Wolfgangsee", "Attersee", "Traunsee"], anz: true});
  g("zillertal", "Zillertal", TAL, "alpen", [[47.00, 11.60, 47.42, 12.10]], {alias: ["Zillertaler Alpen", "Mayrhofen", "Zell am Ziller"]});
  g("stubaital", "Stubaital", TAL, "alpen", [[46.93, 11.05, 47.20, 11.45]], {alias: ["Stubai", "Stubaier Alpen", "Neustift"]});
  g("oetztal", "Ötztal", TAL, "alpen", [[46.75, 10.85, 47.25, 11.15]], {alias: ["Oetztal", "Ötztaler Alpen", "Sölden", "Obergurgl"]});
  g("paznaun", "Paznaun", TAL, "alpen", [[46.85, 10.10, 47.12, 10.55]], {alias: ["Paznauntal", "Ischgl", "Galtür"]});
  g("montafon", "Montafon", TAL, "alpen", [[46.82, 9.78, 47.15, 10.10]], {alias: ["Silvretta", "Schruns"]});
  g("kaunertal", "Kaunertal", TAL, "alpen", [[46.80, 10.58, 47.08, 10.78]], {alias: ["Kaunertaler Gletscher", "Gepatschhaus"]});
  g("kitzbueheler", "Kitzbüheler Alpen", GEB, "alpen", [[47.28, 12.00, 47.56, 12.65]], {alias: ["Kitzbühel", "Kitzbuehel", "Brixental", "Wildschönau", "Saalbach"]});
  g("wilder-kaiser", "Wilder Kaiser", GEB, "alpen", [[47.50, 12.17, 47.64, 12.47]], {alias: ["Kaisergebirge", "Ellmau", "Kaiser", "Kaiserwinkl", "Kirchdorf in Tirol", "St. Johann in Tirol", "Going"]});        // 3.68.0: bis 12.47 E: Kirchdorf in Tirol und St. Johann am Ostrand des Kaisers (vorher nur Kitzbüheler Alpen)
  g("karwendel", "Karwendel", GEB, "alpen", [[47.28, 11.18, 47.56, 11.78]], {alias: ["Karwendelgebirge", "Achensee", "Scharnitz", "Hinterriß"]});
  g("dachstein", "Dachstein", GEB, "alpen", [[47.38, 13.45, 47.58, 13.80]], {alias: ["Dachsteingebirge", "Hallstatt", "Gosau", "Ramsau am Dachstein"]});
  g("hochkoenig", "Hochkönig", GEB, "alpen", [[47.33, 12.85, 47.48, 13.15]], {alias: ["Hochkoenig", "Maria Alm", "Dienten"]});
  g("hohetauern", "Hohe Tauern", GEB, "alpen", [[46.85, 12.10, 47.35, 13.35]], {alias: ["Nationalpark Hohe Tauern", "Hohen Tauern"]});
  g("glockner", "Großglockner", GEB, "hohetauern", [[46.95, 12.60, 47.20, 12.95]], {alias: ["Grossglockner", "Glockner", "Kals", "Heiligenblut", "Pasterze"]});
  g("venediger", "Venedigergruppe", GEB, "hohetauern", [[46.95, 12.15, 47.24, 12.55]], {alias: ["Venediger", "Großvenediger", "Prägraten", "Krimmler Tauern"]});
  /* 3.68.0 Niedere Tauern (Oberbegriff) mit Schladminger und Radstädter Tauern; Maltatal (Ankogel-/Hochalmgruppe, Kärnten); Gailtaler Alpen (nördlich des Gailtals) */
  g("niedere-tauern", "Niedere Tauern", GEB, "alpen", [], {alias: ["Niedere Tauern Steiermark"]});
  g("schladminger", "Schladminger Tauern", GEB, "niedere-tauern", [[47.25, 13.50, 47.47, 14.20]], {alias: ["Schladming", "Haus im Ennstal", "Aich", "Rohrmoos", "Untertal", "Planai", "Irdning-Donnersbachtal", "Donnersbachtal", "Giglachsee", "Hochwurzen"],
                                                                  nicht: [[47.405, 13.45, 47.47, 13.66]]});          // nicht: Ramsau am Dachstein bleibt beim Dachstein
  g("radstaedter", "Radstädter Tauern", GEB, "niedere-tauern", [[47.20, 13.45, 47.32, 13.65]], {alias: ["Radstaedter Tauern", "Obertauern", "Untertauern", "Radstädter Tauernpass"]});
  g("maltatal", "Maltatal", TAL, "hohetauern", [[46.95, 13.30, 47.10, 13.60]], {alias: ["Malta", "Kölnbreinsperre", "Koelnbreinsperre", "Maltatal Kärnten", "Hochalmspitze", "Maltaberg"]});
  g("gailtaler", "Gailtaler Alpen", GEB, "alpen", [[46.68, 13.05, 46.82, 13.70]], {alias: ["Gailtaler Alpen Kärnten", "Kleblach-Lind", "Lind im Drautal", "Oberdrautal", "Reißkofel", "Dobratsch", "Greifenburg"]});
  g("nockberge", "Nockberge", GEB, "alpen", [[46.75, 13.70, 47.00, 14.10]], {alias: ["Nockalm", "Nockalmstraße", "Bad Kleinkirchheim", "Turracher Höhe"]});
  g("gesaeuse", "Gesäuse", GEB, "alpen", [[47.48, 14.45, 47.68, 14.75]], {alias: ["Gesaeuse", "Nationalpark Gesäuse", "Admont", "Johnsbach"]});
  g("hochschwab", "Hochschwab", GEB, "alpen", [[47.50, 14.95, 47.72, 15.40]], {alias: ["Hochschwabgruppe", "Aflenz"]});
  g("rax", "Rax und Schneeberg", GEB, "alpen", [[47.60, 15.60, 47.84, 16.02]], {alias: ["Rax", "Raxalpe", "Schneeberg", "Semmering", "Wiener Hausberge"]});
  g("bregenzerwald", "Bregenzerwald", TAL, "alpen", [[47.25, 9.78, 47.52, 10.10]], {alias: ["Bregenzer Wald", "Bezau", "Schoppernau"]});
  g("kleinwalsertal", "Kleinwalsertal", TAL, "alpen", [[47.28, 10.12, 47.40, 10.27]], {alias: ["Walsertal", "Riezlern"]});
  g("arlberg", "Arlberg", GEB, "alpen", [[47.05, 10.08, 47.25, 10.35]], {alias: ["St. Anton", "Lech", "Zürs"]});
  g("ausserfern", "Außerfern", REG, "alpen", [[47.08, 10.35, 47.58, 11.00]], {alias: ["Ausserfern", "Reutte", "Lechtal", "Lechtaler Alpen", "Tannheimer Tal", "Ehrwald"], county: ["Reutte"], anz: true});

  /* 3.69.0 Österreich ergänzt: Osttirol (Bezirk Lienz) mit Villgratental, Defereggen, Virgental und Lienzer Dolomiten; Innsbruck/Mittelgebirge und Tuxer Voralpen; Rätikon mit Brandnertal;
     Ötscher, Wachau, Neusiedler See, Villach/Ossiacher See. Näherungen wie alle Gebiete; Osttirol und seine Täler schließen Südtirol über `nicht` aus (der Bezirk Lienz steht in dessen nichtKreis). */
  g("osttirol", "Osttirol", REG, "alpen", [], {poly: [[[47.07, 12.14], [47.10, 12.28], [47.12, 12.42], [47.10, 12.58], [47.09, 12.70], [47.04, 12.75], [46.98, 12.79], [46.90, 12.83], [46.84, 12.86], [46.80, 12.92], [46.76, 12.93],
                                                      [46.72, 12.82], [46.71, 12.70], [46.665, 12.66], [46.665, 12.50], [46.70, 12.45], [46.745, 12.37], [46.77, 12.33], [46.80, 12.29], [46.85, 12.27], [46.95, 12.20]]],
                                  alias: ["East Tyrol", "Osttirol Lienz", "Bezirk Lienz", "Lienz", "Matrei in Osttirol", "Matrei", "Sillian", "Kals am Großglockner", "Obertilliach", "Kartitsch"], county: ["Lienz"], nicht: ["suedtirol"], anz: true});
  g("villgratental", "Villgratental", TAL, "osttirol", [], {poly: [[[46.745, 12.45], [46.745, 12.37], [46.77, 12.33], [46.80, 12.29], [46.85, 12.27], [46.88, 12.30], [46.88, 12.46]]],
                                  alias: ["Villgraten", "Innervillgraten", "Außervillgraten", "Ausservillgraten", "Kalkstein", "Villgrater Berge", "Hochgrubbachspitze"], nicht: ["suedtirol"]});
  g("defereggen", "Defereggental", TAL, "osttirol", [[46.86, 12.25, 46.99, 12.55]], {alias: ["Defereggen", "Deferegger Alpen", "St. Jakob in Defereggen", "St. Veit in Defereggen", "Hopfgarten in Defereggen", "Staller Sattel"], nicht: ["suedtirol"]});
  g("virgental", "Virgental", TAL, "osttirol", [[46.99, 12.28, 47.10, 12.50]], {alias: ["Virgen", "Prägraten am Großvenediger", "Praegraten", "Umbalfälle", "Johannishütte", "Neue Prager Hütte"], nicht: ["suedtirol"]});
  g("lienzer-dolomiten", "Lienzer Dolomiten", GEB, "osttirol", [[46.73, 12.70, 46.82, 12.86]], {alias: ["Lienzer Dolomiten Osttirol", "Dolomitenhütte", "Karlsbader Hütte", "Laserzwand", "Spitzkofel", "Lienzer Hütte"]});
  g("innsbruck", "Innsbruck und Mittelgebirge", REG, "alpen", [[47.17, 11.28, 47.31, 11.50]], {alias: ["Innsbrucker Mittelgebirge", "Mittelgebirge", "Innsbruck", "Igls", "Patsch", "Aldrans", "Lans", "Rinn", "Mutters", "Axams", "Patscherkofel", "Nordkette", "Hungerburg", "Ellbögen"], anz: true});
  g("tuxer", "Tuxer Voralpen", GEB, "alpen", [[47.12, 11.42, 47.31, 11.80]], {alias: ["Tuxer Alpen", "Patscherkofel", "Glungezer", "Tulfes", "Tulfein", "Volderer Berg", "Kellerjoch", "Lizum"]});
  g("raetikon", "Rätikon", GEB, "alpen", [[46.93, 9.52, 47.14, 9.88]], {alias: ["Raetikon", "Lünersee", "Luenersee", "Schesaplana", "Drei Türme", "Rellstal", "Gargellen", "Madrisa", "Bürserberg", "Brand", "Bürs", "Nenzing", "Gamperdonatal"]});
  g("brandnertal", "Brandnertal", TAL, "raetikon", [[47.04, 9.66, 47.17, 9.86]], {alias: ["Brand", "Bürserberg", "Burserberg", "Bürs", "Brandner Tal", "Lünersee", "Bludenz", "Nüziders", "Dalaas"]});
  g("oetscher", "Ötscher und Mostviertler Alpen", GEB, "alpen", [[47.80, 15.05, 47.95, 15.35]], {alias: ["Ötscher", "Oetscher", "Dürrenstein", "Lunz am See", "Lackenhof", "Gemeindealpe", "Annaberg", "Ötschergräben", "Wilder Mann"]});
  g("wachau", "Wachau", REG, null, [[48.20, 15.25, 48.45, 15.62]], {alias: ["Wachau Donau", "Dürnstein", "Duernstein", "Spitz an der Donau", "Weißenkirchen", "Melk", "Krems an der Donau", "Rossatzbach", "Arnsdorf", "Wachauer Welterbesteig"], anz: true});
  g("neusiedlersee", "Neusiedler See", REG, null, [[47.62, 16.62, 47.98, 16.95]], {alias: ["Neusiedlersee", "Fertő", "Fertö", "Seewinkel", "Illmitz", "Podersdorf", "Rust", "Breitenbrunn", "Mörbisch", "Weiden am See", "Apetlon"], anz: true});
  g("villach", "Villach und Ossiacher See", REG, "alpen", [[46.58, 13.80, 46.76, 14.05]], {alias: ["Villach", "Gerlitzen", "Gerlitzen Alpe", "Ossiacher See", "Ossiach", "Annenheim", "Treffen", "Bodensdorf", "Landskron", "Verditz"], anz: true});

  /* ===================== Alpen: Deutschland ===================== */
  g("allgaeu", "Allgäu", REG, "alpen", [[47.32, 10.00, 47.95, 10.78]], {alias: ["Allgaeu", "Allgäuer Alpen", "Oberstdorf", "Kempten"], anz: true});
  g("berchtesgaden", "Berchtesgadener Land", REG, "alpen", [[47.48, 12.70, 47.78, 13.12]], {alias: ["Berchtesgaden", "Watzmann", "Königssee", "Bad Reichenhall"], county: ["Berchtesgadener Land"], anz: true});
  g("wetterstein", "Wetterstein", GEB, "alpen", [[47.38, 10.90, 47.56, 11.30]], {alias: ["Wettersteingebirge", "Zugspitze", "Garmisch-Partenkirchen", "Mittenwald", "Zugspitzregion"]});
  g("chiemgau", "Chiemgau", REG, "alpen", [[47.65, 12.35, 47.95, 12.80]], {alias: ["Chiemgauer Alpen", "Chiemsee", "Ruhpolding", "Reit im Winkl"], anz: true});
  g("tegernsee", "Tegernsee und Schliersee", GEB, "alpen", [[47.60, 11.62, 47.78, 12.08]], {alias: ["Tegernsee", "Schliersee", "Mangfallgebirge", "Spitzingsee", "Wendelstein", "Bayrischzell"]});
  g("ammergau", "Ammergauer Alpen", GEB, "alpen", [[47.50, 10.62, 47.68, 11.15]], {alias: ["Ammergebirge", "Oberammergau", "Füssen", "Neuschwanstein", "Linderhof", "Plansee"]});

  /* ===================== Alpen: Schweiz ===================== */
  g("wallis", "Wallis", REG, "alpen", [], {poly: [[[46.40, 6.86], [46.20, 6.80], [46.05, 6.90], [45.97, 6.98], [45.92, 7.05], [45.87, 7.17], [45.93, 7.35], [45.93, 7.70], [45.93, 7.87], [46.00, 8.05], [46.18, 8.10], [46.30, 8.45],
                                [46.58, 8.45], [46.58, 8.40], [46.57, 8.25], [46.54, 8.02], [46.47, 7.80], [46.42, 7.60], [46.37, 7.40], [46.33, 7.20], [46.33, 7.00]]],
                                alias: ["Valais", "Zermatt", "Matterhorn", "Saas-Fee", "Aletsch"], anz: true});
  g("bernoberland", "Berner Oberland", GEB, "alpen", [[46.40, 7.15, 46.85, 8.40]], {alias: ["Bernese Oberland", "Interlaken", "Grindelwald", "Lauterbrunnen", "Kandersteg", "Adelboden", "Gstaad"]});
  g("jungfrau", "Jungfrau-Region", GEB, "bernoberland", [[46.50, 7.80, 46.68, 8.15]], {alias: ["Jungfrauregion", "Jungfraujoch", "Eiger", "Mönch", "Wengen", "Mürren", "Kleine Scheidegg"]});
  g("tessin", "Tessin", REG, "alpen", [], {poly: [[[46.50, 8.40], [46.57, 8.70], [46.56, 8.95], [46.45, 9.05], [46.22, 9.08], [45.83, 9.05], [45.83, 8.92], [46.00, 8.80], [46.10, 8.70], [46.25, 8.50], [46.40, 8.38]]],
                                  alias: ["Ticino", "Lugano", "Locarno", "Bellinzona", "Verzasca", "Maggiatal"], anz: true});
  g("graubuenden", "Graubünden", REG, "alpen", [[46.22, 8.70, 47.07, 10.50]], {alias: ["Graubuenden", "Grisons", "Grigioni", "Chur", "Davos", "Arosa", "Flims"], nicht: ["tessin", [46.20, 9.30, 46.31, 10.50], [46.34, 10.10, 46.62, 10.50]], anz: true});
  g("engadin", "Engadin", TAL, "graubuenden", [[46.38, 9.65, 46.95, 10.50]], {alias: ["Engiadina", "Oberengadin", "Unterengadin", "St. Moritz", "Pontresina", "Scuol", "Zernez", "Bernina"], nicht: [[46.34, 10.10, 46.62, 10.50]]});
  g("zentralschweiz", "Zentralschweiz", REG, "alpen", [[46.62, 8.05, 47.12, 8.85]], {alias: ["Innerschweiz", "Luzern", "Vierwaldstättersee", "Pilatus", "Rigi", "Engelberg", "Titlis", "Andermatt"]});
  g("appenzell", "Appenzell und Alpstein", GEB, "alpen", [[47.17, 9.15, 47.45, 9.60]], {alias: ["Appenzell", "Alpstein", "Säntis", "Appenzeller Land", "Toggenburg"]});

  /* ===================== Alpen: Italien, Frankreich, Slowenien ===================== */
  g("suedtirol", "Südtirol", REG, "alpen", [], {poly: [[[46.87, 10.50], [46.78, 10.72], [46.77, 10.85], [46.83, 10.95], [46.91, 11.09], [46.96, 11.15], [47.00, 11.30], [47.00, 11.52], [47.00, 11.75], [47.03, 11.95],
                                                         [47.08, 12.12], [46.95, 12.20], [46.85, 12.27], [46.80, 12.29], [46.77, 12.33], [46.745, 12.37], [46.70, 12.45], [46.65, 12.43], [46.62, 12.34], [46.58, 12.20], [46.57, 12.05], [46.52, 11.99],
                                                         [46.50, 11.88], [46.49, 11.80], [46.50, 11.76], [46.47, 11.65], [46.41, 11.58], [46.36, 11.55], [46.30, 11.40], [46.24, 11.22], [46.30, 11.15],
                                                         [46.43, 11.19], [46.51, 11.07], [46.47, 10.95], [46.45, 10.80], [46.45, 10.62], [46.51, 10.54], [46.55, 10.46], [46.65, 10.38], [46.78, 10.40]]],
                                      alias: ["Alto Adige", "South Tyrol", "Sudtirol", "Provinz Bozen", "Bolzano"], county: ["Bozen", "Bolzano", "Bolzano - Bozen", "Bozen - Südtirol", "Südtirol", "Alto Adige"], anz: true,
                                      /* 3.68.0: nur die Provinz Bozen. Osttirol (Sillian, Innervillgraten: Bezirk Lienz) und das Val di Rabbi (Trentino) liegen am Rand des Vielecks; bei Touren mit Bezirk entscheidet er, sonst nur die Koordinate */
                                      nichtKreis: ["Lienz", "Trient", "Trento", "Belluno", "Sondrio", "Landeck", "Imst", "Innsbruck-Land", "Schwaz", "Engiadina Bassa/Val Müstair"]});
  g("trentino", "Trentino", REG, "alpen", [], {poly: [[[46.50, 10.60], [46.50, 11.95], [46.20, 11.95], [46.00, 11.78], [45.95, 11.40], [45.78, 11.20], [45.68, 11.00], [45.80, 10.75], [45.85, 10.62],
                                                        [46.05, 10.50], [46.20, 10.55], [46.30, 10.62]]],
                                     alias: ["Provinz Trient", "Trient", "Trento"], county: ["Trient", "Trento"], nicht: ["suedtirol"], anz: true});
  g("dolomiten", "Dolomiten", GEB, "alpen", [[46.22, 11.55, 46.72, 12.45]], {alias: ["Dolomiti", "Dolomites", "Drei Zinnen", "Seiser Alm", "Cortina d'Ampezzo", "Rosengarten", "Langkofel", "Marmolada"]});
  g("brenta", "Brenta-Dolomiten", GEB, "alpen", [[46.07, 10.80, 46.26, 11.00]], {alias: ["Brenta", "Madonna di Campiglio", "Molveno"]});
  g("ortler", "Ortler", GEB, "alpen", [[46.38, 10.40, 46.62, 10.78]], {alias: ["Ortlergruppe", "Ortles", "Sulden", "Stilfser Joch", "Martelltal", "Cevedale"]});
  g("gardasee", "Gardasee", REG, "alpen", [[45.43, 10.45, 45.93, 10.95]], {alias: ["Lago di Garda", "Lake Garda", "Riva del Garda", "Malcesine", "Monte Baldo", "Torbole"], anz: true});
  g("aostatal", "Aostatal", REG, "alpen", [[45.47, 6.80, 45.99, 7.88]], {alias: ["Valle d'Aosta", "Vallée d'Aoste", "Aosta Valley", "Aosta", "Courmayeur", "Cervinia"], nicht: [[45.855, 6.70, 46.0, 7.06]], anz: true});
  g("piemont", "Piemont", REG, null, [], {poly: [[[46.40, 8.42], [46.10, 8.72], [45.80, 8.55], [45.45, 8.65], [45.30, 8.85], [44.90, 8.80], [44.60, 8.60], [44.45, 8.40], [44.15, 7.95], [44.15, 7.55],
                                                    [44.45, 6.95], [44.65, 6.85], [44.95, 6.65], [45.10, 6.65], [45.25, 6.95], [45.40, 7.15], [45.50, 7.40], [45.60, 7.70], [45.85, 7.92], [45.97, 7.97],
                                                    [46.05, 8.12], [46.25, 8.10]]], alias: ["Piemonte", "Piedmont"]});
  g("granparadiso", "Gran Paradiso", GEB, "alpen", [[45.42, 7.10, 45.62, 7.45]], {alias: ["Parco Nazionale Gran Paradiso", "Cogne", "Ceresole Reale", "Valsavarenche"]});
  g("monviso", "Monviso", GEB, "piemont", [[44.55, 6.95, 44.80, 7.25]], {alias: ["Monte Viso", "Mont Viso", "Crissolo", "Pian del Re"]});
  g("monterosa", "Monte Rosa", GEB, "alpen", [[45.78, 7.70, 46.00, 8.05]], {alias: ["Alagna", "Macugnaga", "Gressoney"]});
  g("friaul", "Friaul", REG, null, [], {poly: [[[46.65, 12.45], [46.62, 13.40], [46.52, 13.70], [46.40, 13.55], [46.30, 13.50], [46.18, 13.42], [46.05, 13.55], [45.90, 13.62], [45.78, 13.72], [45.62, 13.78],
                                                 [45.65, 13.40], [45.65, 12.95], [45.70, 12.60], [45.95, 12.42], [46.30, 12.35], [46.50, 12.40]]],
                              alias: ["Friuli", "Friuli Venezia Giulia", "Friuli-Venezia Giulia"], anz: true});
  g("karnische", "Karnische Alpen", GEB, "alpen", [[46.50, 12.45, 46.72, 13.55]], {alias: ["Carnia", "Alpi Carniche", "Plöckenpass", "Nassfeld", "Kötschach-Mauthen"]});
  g("julische", "Julische Alpen", GEB, "alpen", [[46.25, 13.40, 46.52, 14.20]], {alias: ["Julijske Alpe", "Julian Alps", "Triglav", "Bled", "Bohinj", "Bovec", "Kranjska Gora", "Soča"]});
  g("kamniker", "Kamniker Alpen", GEB, "alpen", [[46.28, 14.35, 46.45, 14.80]], {alias: ["Kamniško-Savinjske Alpe", "Savinja Alps", "Steiner Alpen", "Jezersko", "Logarska dolina", "Krvavec"]});
  g("savoyen", "Savoyen", REG, "alpen", [[45.12, 5.75, 46.42, 7.06]], {alias: ["Savoie", "Haute-Savoie", "Savoy"], county: ["Savoie", "Haute-Savoie"], nicht: [[45.10, 5.70, 45.40, 6.10], [46.17, 6.05, 46.26, 6.19]], anz: true});
  g("montblanc", "Mont Blanc", GEB, "alpen", [[45.70, 6.65, 46.08, 7.15]], {alias: ["Mont-Blanc", "Monte Bianco", "Chamonix", "Courmayeur", "Tour du Mont Blanc", "Les Houches", "Argentière"]});
  g("vercors", "Vercors", GEB, "alpen", [[44.75, 5.20, 45.20, 5.70]], {alias: ["Villard-de-Lans", "Parc du Vercors"]});
  g("chartreuse", "Chartreuse", GEB, "alpen", [[45.25, 5.70, 45.55, 5.95]], {alias: ["Massif de la Chartreuse", "Grand Som", "Saint-Pierre-de-Chartreuse"]});
  g("belledonne", "Belledonne", GEB, "alpen", [[45.10, 5.88, 45.55, 6.15]], {alias: ["Chaîne de Belledonne", "Chamrousse", "Allevard"]});
  g("ecrins", "Écrins und Oisans", GEB, "alpen", [[44.65, 6.00, 45.15, 6.55]], {alias: ["Ecrins", "Écrins", "Oisans", "La Bérarde", "La Grave", "Les Deux Alpes", "Vallouise", "Pelvoux", "Barre des Écrins"]});
  g("mercantour", "Mercantour und Seealpen", GEB, "alpen", [[44.00, 6.60, 44.45, 7.45]], {alias: ["Mercantour", "Alpes-Maritimes", "Seealpen", "Saint-Martin-Vésubie", "Barcelonnette", "Vallée des Merveilles", "Isola 2000"]});
  g("vanoise", "Vanoise und Tarentaise", GEB, "alpen", [[45.25, 6.40, 45.70, 7.05]], {alias: ["Vanoise", "Tarentaise", "Pralognan-la-Vanoise", "Val d'Isère", "Tignes", "Les Arcs", "Courchevel", "Méribel", "Val Thorens"]});
  g("queyras", "Queyras", GEB, "alpen", [[44.58, 6.65, 44.88, 7.05]], {alias: ["Parc du Queyras", "Saint-Véran", "Abriès"]});

  /* ===================== Mittelgebirge Deutschland ===================== */
  g("harz", "Harz", GEB, null, [[51.50, 10.20, 51.92, 11.30]], {alias: ["Harzgebirge", "Brocken", "Wernigerode", "Goslar", "Bad Harzburg"]});
  g("hochharz", "Hochharz", GEB, "harz", [[51.72, 10.50, 51.86, 10.78]], {alias: ["Nationalpark Harz", "Brocken", "Schierke", "Torfhaus"]});
  g("suedharz", "Südharz", GEB, "harz", [[51.45, 10.40, 51.65, 11.35]], {alias: ["Suedharz", "Nordhausen", "Bad Lauterberg"]});
  g("elbsandstein", "Elbsandsteingebirge", GEB, null, [], {alias: ["Elbe Sandstone Mountains"]});
  g("saechsische-schweiz", "Sächsische Schweiz", GEB, "elbsandstein", [[50.88, 13.90, 51.03, 14.50]], {alias: ["Saechsische Schweiz", "Saxon Switzerland", "Bastei", "Bad Schandau", "Königstein", "Hinterhermsdorf"]});
  g("boehmische-schweiz", "Böhmische Schweiz", GEB, "elbsandstein", [[50.72, 14.10, 50.90, 14.55]], {alias: ["Boehmische Schweiz", "České Švýcarsko", "Bohemian Switzerland", "Hřensko", "Pravčická brána", "Děčín"]});
  g("erzgebirge", "Erzgebirge", GEB, null, [], {poly: [[[50.45, 12.25], [50.62, 12.45], [50.72, 12.90], [50.82, 13.40], [50.88, 13.90], [50.80, 14.00], [50.62, 13.85], [50.45, 13.35], [50.33, 12.90], [50.28, 12.50], [50.33, 12.25]]],
                                    alias: ["Krušné hory", "Ore Mountains", "Fichtelberg", "Oberwiesenthal", "Altenberg", "Seiffen"]});
  g("thueringer-wald", "Thüringer Wald", GEB, null, [], {poly: [[[51.05, 10.44], [50.78, 10.85], [50.58, 11.27], [50.42, 11.03], [50.62, 10.61], [50.89, 10.20]]], alias: ["Thueringer Wald", "Rennsteig", "Oberhof", "Inselsberg", "Thuringian Forest"]});
  g("rhoen", "Rhön", GEB, null, [[50.25, 9.70, 50.75, 10.35]], {alias: ["Rhoen", "Wasserkuppe", "Hohe Rhön", "Bischofsheim"]});
  g("schwarzwald", "Schwarzwald", GEB, null, [], {poly: [[[47.60, 7.60], [47.85, 7.65], [48.10, 7.80], [48.35, 7.85], [48.50, 7.98], [48.70, 8.12], [48.85, 8.30], [48.95, 8.40], [48.95, 8.80], [48.65, 8.78],
                                                          [48.45, 8.72], [48.20, 8.70], [48.00, 8.62], [47.75, 8.50], [47.62, 8.35], [47.58, 8.00]]], alias: ["Black Forest", "Forêt-Noire"]});
  g("schwarzwald-sued", "Südschwarzwald", GEB, "schwarzwald", [[47.50, 7.50, 48.03, 8.75]], {in: "schwarzwald", alias: ["Suedschwarzwald", "Southern Black Forest"]});
  g("schwarzwald-mittel", "Mittelschwarzwald", GEB, "schwarzwald", [[48.03, 7.50, 48.38, 8.75]], {in: "schwarzwald", alias: ["Central Black Forest"]});
  g("schwarzwald-nord", "Nordschwarzwald", GEB, "schwarzwald", [[48.38, 7.50, 49.00, 8.85]], {in: "schwarzwald", alias: ["Northern Black Forest", "Baiersbronn", "Hornisgrinde"]});
  g("feldberg", "Feldberg (Schwarzwald)", GEB, "schwarzwald-sued", [[47.80, 7.92, 47.93, 8.22]], {alias: ["Feldberg", "Feldbergregion", "Titisee", "Schluchsee"]});
  g("schwaebische-alb", "Schwäbische Alb", GEB, null, [], {poly: [[[47.95, 8.70], [48.30, 8.80], [48.50, 9.15], [48.60, 9.45], [48.65, 9.80], [48.80, 10.10], [48.88, 10.45], [48.65, 10.55], [48.45, 10.15],
                                                                    [48.30, 9.70], [48.15, 9.35], [48.05, 9.10], [47.95, 8.85]]], alias: ["Schwaebische Alb", "Swabian Jura", "Swabian Alb", "Albtrauf"]});
  g("pfaelzerwald", "Pfälzerwald", GEB, null, [[49.08, 7.55, 49.52, 8.20]], {alias: ["Pfälzer Wald", "Pfaelzerwald", "Palatinate Forest", "Haardt", "Dahn", "Annweiler"]});
  g("eifel", "Eifel", GEB, null, [[49.95, 6.15, 50.60, 7.25]], {alias: ["Nordeifel", "Vulkaneifel", "Monschau", "Gerolstein", "Daun"]});
  g("hoheeifel", "Hohe Eifel", GEB, "eifel", [[50.25, 6.80, 50.45, 7.15]], {alias: ["Nürburg", "Hohe Acht", "Adenau"]});
  g("hunsrueck", "Hunsrück", GEB, null, [[49.60, 6.95, 50.10, 7.70]], {alias: ["Hunsrueck", "Soonwald", "Erbeskopf", "Idar-Oberstein"]});
  g("taunus", "Taunus", GEB, null, [], {poly: [[[49.97, 7.80], [50.08, 8.20], [50.15, 8.45], [50.19, 8.58], [50.30, 8.72], [50.40, 8.70], [50.40, 8.10], [50.35, 7.75], [50.15, 7.75]]], alias: ["Großer Feldberg", "Hochtaunus", "Rheingau-Taunus"]});
  g("sauerland", "Sauerland", GEB, null, [[50.95, 7.60, 51.45, 8.80]], {alias: ["Winterberg", "Kahler Asten", "Schmallenberg", "Rothaargebirge"]});
  g("teutoburger-wald", "Teutoburger Wald", GEB, null, [], {poly: [[[52.34, 7.45], [52.23, 8.05], [52.12, 8.50], [51.97, 8.84], [51.83, 9.05], [51.70, 9.00], [51.85, 8.80], [52.00, 8.45], [52.10, 8.00], [52.22, 7.45]]],
                                                              alias: ["Teutoburg Forest", "Hermannsdenkmal", "Externsteine", "Eggegebirge"]});
  g("bayerischer-wald", "Bayerischer Wald", GEB, null, [[48.70, 12.75, 49.25, 13.75]], {alias: ["Bavarian Forest", "Arber", "Großer Arber", "Lusen", "Zwiesel", "Bayerisch Eisenstein"]});
  g("fichtelgebirge", "Fichtelgebirge", GEB, null, [[49.88, 11.60, 50.25, 12.25]], {alias: ["Ochsenkopf", "Wunsiedel", "Bischofsgrün"]});
  g("fraenkische-schweiz", "Fränkische Schweiz", GEB, null, [[49.62, 11.10, 49.97, 11.55]], {alias: ["Fraenkische Schweiz", "Franconian Switzerland", "Pottenstein", "Muggendorf", "Gößweinstein"]});
  g("odenwald", "Odenwald", GEB, null, [[49.35, 8.60, 49.85, 9.40]], {alias: ["Michelstadt", "Erbach", "Lindenfels"]});
  g("spessart", "Spessart", GEB, null, [[49.80, 9.10, 50.25, 9.65]], {alias: ["Aschaffenburg", "Lohr am Main", "Bad Orb"]});
  g("westerwald", "Westerwald", GEB, null, [[50.40, 7.60, 50.80, 8.20]], {alias: ["Montabaur", "Westerburg", "Hachenburg"]});
  g("siebengebirge", "Siebengebirge", GEB, null, [[50.60, 7.15, 50.75, 7.35]], {alias: ["Drachenfels", "Königswinter", "Ölberg"]});
  g("weserbergland", "Weserbergland", GEB, null, [[51.40, 8.90, 52.30, 9.75]], {alias: ["Hameln", "Bad Pyrmont", "Höxter", "Porta Westfalica"]});
  g("solling", "Solling", GEB, "weserbergland", [[51.65, 9.45, 51.85, 9.80]], {alias: ["Uslar", "Holzminden", "Neuhaus im Solling"]});
  g("vogelsberg", "Vogelsberg", GEB, null, [[50.35, 9.00, 50.80, 9.50]], {alias: ["Hoherodskopf", "Schotten", "Lauterbach"]});
  g("frankenwald", "Frankenwald", GEB, null, [[50.20, 11.25, 50.55, 11.85]], {alias: ["Kronach", "Naila", "Bad Steben"]});
  g("oberpfaelzer-wald", "Oberpfälzer Wald", GEB, null, [[49.30, 12.10, 49.80, 12.90]], {alias: ["Oberpfaelzer Wald", "Waldmünchen", "Vohenstrauß"]});
  g("steigerwald", "Steigerwald", GEB, null, [[49.65, 10.30, 50.00, 10.65]], {alias: ["Ebrach", "Scheinfeld"]});
  g("kellerwald", "Kellerwald", GEB, null, [[50.95, 8.90, 51.25, 9.30]], {alias: ["Edersee", "Kellerwald-Edersee", "Bad Wildungen"]});
  g("lueneburger-heide", "Lüneburger Heide", REG, null, [[52.75, 9.50, 53.35, 10.50]], {alias: ["Lueneburger Heide", "Wilsede", "Südheide", "Soltau", "Bispingen"]});
  g("hegau", "Hegau", REG, null, [[47.70, 8.60, 47.95, 9.05]], {alias: ["Hohentwiel", "Singen", "Engen"]});
  g("moseltal", "Moseltal", TAL, null, [[49.72, 6.55, 49.84, 6.80], [49.78, 6.75, 49.92, 6.98], [49.86, 6.90, 49.97, 7.15], [49.94, 7.05, 50.08, 7.28], [50.00, 7.10, 50.20, 7.25],
                                        [50.12, 7.12, 50.34, 7.55], [50.30, 7.45, 50.38, 7.62]], {alias: ["Mosel", "Moselle", "Trier", "Bernkastel-Kues", "Cochem", "Zell (Mosel)"]});

  /* ===================== Mittelgebirge Europa ===================== */
  g("karpaten", "Karpaten", GEB, null, [], {alias: ["Karpaty", "Carpathians", "Carpați", "Karpathen"]});
  g("vogesen", "Vogesen", GEB, null, [[47.78, 6.65, 48.70, 7.45], [48.65, 7.10, 49.05, 7.85]], {alias: ["Vosges", "Vogezen", "Grand Ballon", "Hohneck", "Gérardmer"]});
  g("jura", "Jura", GEB, null, [[46.10, 5.70, 46.50, 6.05], [46.45, 5.90, 46.95, 6.50], [46.90, 6.30, 47.30, 7.10], [47.10, 7.00, 47.45, 7.80], [47.35, 7.60, 47.55, 8.30]],
    {alias: ["Juragebirge", "Jura Mountains", "Chasseral", "Vallée de Joux", "Pontarlier"]});
  g("auvergne", "Auvergne", REG, null, [[44.70, 2.20, 46.10, 3.95]], {alias: ["Massif Central", "Chaîne des Puys", "Puy de Dôme", "Volcans d'Auvergne", "Sancy", "Cantal"], anz: true});
  g("cevennen", "Cevennen", GEB, null, [[43.95, 3.35, 44.55, 4.25]], {alias: ["Cévennes", "Cevennes", "Mont Lozère", "Mont Aigoual", "Florac"]});
  g("ardennen", "Ardennen", GEB, null, [[49.72, 4.70, 50.50, 6.15]], {alias: ["Ardennes", "Ardenne", "Houffalize", "La Roche-en-Ardenne", "Bouillon", "Ösling", "Oesling"]});
  g("hohesvenn", "Hohes Venn", GEB, null, [[50.40, 5.95, 50.65, 6.30]], {alias: ["Hautes Fagnes", "Hoge Venen", "Venn", "Baraque Michel", "Botrange", "Eupen"]});
  g("ostbelgien", "Ostbelgien", REG, null, [[50.20, 5.95, 50.75, 6.35]], {alias: ["Deutschsprachige Gemeinschaft", "Eupen", "Sankt Vith", "Sankt-Vith", "Büllingen"], anz: true});
  g("muellerthal", "Luxemburger Schweiz", GEB, null, [[49.75, 6.20, 49.90, 6.50]], {alias: ["Müllerthal", "Muellerthal", "Mullerthal", "Petite Suisse luxembourgeoise", "Echternach", "Berdorf"]});
  g("tatra", "Tatra", GEB, "karpaten", [], {alias: ["Tatry", "Tatras", "High Tatras"]});
  g("riesengebirge", "Riesengebirge", GEB, null, [[50.68, 15.30, 50.88, 15.90]], {alias: ["Krkonoše", "Krkonose", "Karkonosze", "Giant Mountains", "Schneekoppe", "Sněžka", "Špindlerův Mlýn", "Harrachov", "Karpacz"]});
  g("isergebirge", "Isergebirge", GEB, null, [[50.75, 14.95, 50.95, 15.45]], {alias: ["Jizerské hory", "Jizerske hory", "Góry Izerskie", "Jizera Mountains", "Jizerka", "Świeradów-Zdrój"]});
  g("adlergebirge", "Adlergebirge", GEB, null, [[50.10, 16.15, 50.45, 16.60]], {alias: ["Orlické hory", "Orlicke hory", "Góry Orlickie", "Eagle Mountains", "Deštné"]});
  g("altvater", "Altvatergebirge", GEB, null, [[49.95, 17.00, 50.35, 17.50]], {alias: ["Jeseníky", "Jeseniky", "Hrubý Jeseník", "Praděd", "Altvater", "Hoher Gesenke"]});
  g("beskiden", "Beskiden", GEB, "karpaten", [[49.35, 18.00, 49.90, 19.60], [49.35, 19.60, 49.85, 21.80]], {alias: ["Beskidy", "Beskydy", "Beskids", "Lysá hora", "Babia Góra", "Szczyrk", "Żywiec"]});
  g("boehmerwald", "Böhmerwald", GEB, null, [[48.60, 13.25, 49.30, 14.50]], {alias: ["Boehmerwald", "Šumava", "Sumava", "Bohemian Forest", "Lipno", "Nationalpark Šumava"]});
  g("boehmisches-paradies", "Böhmisches Paradies", GEB, null, [[50.43, 15.05, 50.62, 15.40]], {alias: ["Boehmisches Paradies", "Český ráj", "Cesky raj", "Bohemian Paradise", "Hrubá Skála", "Turnov"]});
  g("boehmisches-mittelgebirge", "Böhmisches Mittelgebirge", GEB, null, [[50.40, 13.70, 50.78, 14.25]], {alias: ["Boehmisches Mittelgebirge", "České středohoří", "Ceske stredohori", "Bohemian Central Uplands", "Milešovka"]});
  g("hohetatra", "Hohe Tatra", GEB, "tatra", [[49.10, 19.93, 49.28, 20.35]], {alias: ["Vysoké Tatry", "Vysoke Tatry", "High Tatras", "Tatry Wysokie", "Štrbské Pleso", "Gerlach", "Rysy", "Tatranská Lomnica"]});
  g("westtatra", "Westtatra", GEB, "tatra", [[49.15, 19.55, 49.30, 19.93]], {alias: ["Západné Tatry", "Tatry Zachodnie", "Western Tatras", "Roháče", "Zuberec"]});
  g("zakopane", "Zakopane und polnische Tatra", GEB, "tatra", [[49.20, 19.80, 49.38, 20.10]], {alias: ["Zakopane", "Polnische Tatra", "Polish Tatras", "Podhale", "Kasprowy Wierch", "Morskie Oko"]});
  g("niedere-tatra", "Niedere Tatra", GEB, "karpaten", [[48.80, 19.25, 49.05, 19.95]], {alias: ["Nízke Tatry", "Nizke Tatry", "Low Tatras", "Ďumbier", "Chopok", "Donovaly", "Jasná"]});
  g("grosse-fatra", "Große Fatra", GEB, "karpaten", [[48.85, 18.85, 49.12, 19.22]], {alias: ["Veľká Fatra", "Velka Fatra", "Grosse Fatra", "Greater Fatra"]});
  g("kleine-fatra", "Kleine Fatra", GEB, "karpaten", [[49.13, 18.80, 49.30, 19.15]], {alias: ["Malá Fatra", "Mala Fatra", "Kleine Fatra", "Lesser Fatra", "Terchová", "Vrátna"]});
  g("slowakisches-paradies", "Slowakisches Paradies", GEB, "karpaten", [[48.85, 20.20, 49.02, 20.55]], {alias: ["Slovenský raj", "Slovensky raj", "Slovak Paradise", "Hrabušice", "Dedinky"]});
  g("pieniny", "Pieniny", GEB, "karpaten", [[49.35, 20.30, 49.47, 20.60]], {alias: ["Pienin", "Pieninen", "Szczawnica", "Červený Kláštor", "Trzy Korony"]});
  g("kleine-karpaten", "Kleine Karpaten", GEB, "karpaten", [[48.17, 16.95, 48.60, 17.55]], {alias: ["Malé Karpaty", "Male Karpaty", "Little Carpathians", "Smolenice"]});
  g("eulengebirge", "Eulengebirge", GEB, null, [[50.55, 16.35, 50.75, 16.65]], {alias: ["Góry Sowie", "Gory Sowie", "Owl Mountains", "Sowia Góra"]});
  g("stolowe", "Heuscheuergebirge", GEB, null, [[50.35, 16.10, 50.55, 16.55]], {alias: ["Góry Stołowe", "Gory Stolowe", "Table Mountains", "Szczeliniec", "Kudowa-Zdrój", "Broumovské stěny"]});
  g("bieszczady", "Bieszczady", GEB, "karpaten", [[48.95, 22.10, 49.30, 22.95]], {alias: ["Bieszczady-Gebirge", "Wetlina", "Połonina Caryńska", "Ustrzyki Górne"]});
  g("swietokrzyskie", "Heiligkreuzgebirge", GEB, null, [[50.70, 20.60, 51.10, 21.15]], {alias: ["Świętokrzyskie", "Swietokrzyskie", "Góry Świętokrzyskie", "Heilig Kreuz", "Święty Krzyż"]});
  g("masuren", "Masuren", REG, null, [[53.45, 21.00, 54.30, 22.70]], {alias: ["Mazury", "Masurische Seenplatte", "Masuria", "Mikołajki", "Giżycko"], anz: true});
  g("peakdistrict", "Peak District", GEB, null, [[53.00, -2.05, 53.52, -1.58]], {alias: ["Peak District National Park", "Kinder Scout", "Edale", "Hathersage", "Bakewell"]});
  g("lakedistrict", "Lake District", GEB, null, [[54.20, -3.55, 54.75, -2.80]], {alias: ["Lake District National Park", "Cumbrian Mountains", "Scafell Pike", "Keswick", "Ambleside", "Windermere", "Langdale"]});
  g("snowdonia", "Snowdonia", GEB, null, [[52.60, -4.30, 53.25, -3.60]], {alias: ["Eryri", "Snowdon", "Yr Wyddfa", "Betws-y-Coed", "Llanberis", "Cadair Idris"]});
  g("highlands", "Schottische Highlands", GEB, null, [[56.45, -6.90, 58.60, -3.00]], {alias: ["Highlands", "Scottish Highlands", "Hochland", "Fort William", "Ben Nevis", "Schottland"]});
  g("cairngorms", "Cairngorms", GEB, "highlands", [[56.85, -4.15, 57.30, -3.00]], {alias: ["Cairngorm", "Cairngorms National Park", "Aviemore", "Cairn Gorm", "Braemar"]});
  g("glencoe", "Glencoe", TAL, "highlands", [[56.60, -5.30, 56.75, -4.90]], {alias: ["Glen Coe", "Kinlochleven"]});
  g("skye", "Isle of Skye", INS, "highlands", [[57.03, -6.90, 57.75, -5.72]], {alias: ["Skye", "Insel Skye", "Portree", "Cuillin", "Quiraing", "Old Man of Storr"]});
  g("wicklow", "Wicklow Mountains", GEB, null, [[52.80, -6.60, 53.25, -6.10]], {alias: ["Wicklow", "Glendalough", "Lugnaquilla", "Wicklow Way"]});
  g("kerry", "Kerry", REG, null, [[51.75, -10.50, 52.50, -9.15]], {alias: ["County Kerry", "Ring of Kerry", "Killarney", "Carrauntoohil", "Iveragh"], anz: true});
  g("dingle", "Dingle", KUE, "kerry", [[52.05, -10.50, 52.22, -9.95]], {alias: ["Dingle-Halbinsel", "Dingle Peninsula", "Corca Dhuibhne", "Slea Head"]});
  g("connemara", "Connemara", GEB, null, [[53.30, -10.20, 53.70, -9.40]], {alias: ["Twelve Bens", "Clifden", "Kylemore", "Letterfrack"]});

  /* ===================== Spanien, Portugal ===================== */
  g("pyrenaeen", "Pyrenäen", GEB, null, [], {poly: [[[43.30, -1.80], [43.15, -1.10], [43.15, -0.30], [43.05, 0.50], [42.92, 1.30], [42.85, 2.00], [42.75, 2.60], [42.60, 3.00], [42.35, 3.25], [42.20, 2.80],
                                                      [42.18, 2.20], [42.22, 1.70], [42.30, 1.20], [42.33, 0.70], [42.38, 0.10], [42.50, -0.60], [42.80, -1.40], [43.00, -1.85]]],
                                  alias: ["Pyrenaeen", "Pyrénées", "Pirineos", "Pyrenees", "Pirineus", "Andorra"]});
  g("pyr-aragon", "Aragonische Pyrenäen", GEB, "pyrenaeen", [[42.35, -1.00, 42.85, 0.85]], {alias: ["Aragonische Pyrenaeen", "Pirineo Aragonés", "Aragonese Pyrenees", "Benasque", "Aneto", "Aragón"]});
  g("pyr-katalan", "Katalanische Pyrenäen", GEB, "pyrenaeen", [[42.20, 0.65, 42.82, 1.45], [42.17, 1.45, 42.45, 3.25]], {alias: ["Katalanische Pyrenaeen", "Pirineu Català", "Catalan Pyrenees", "Katalonien", "Cerdanya", "Val d'Aran"]});
  g("ordesa", "Ordesa", GEB, "pyr-aragon", [[42.58, -0.20, 42.75, 0.12]], {alias: ["Ordesa y Monte Perdido", "Monte Perdido", "Torla", "Pineta", "Nationalpark Ordesa"]});
  g("aiguestortes", "Aigüestortes", GEB, "pyr-katalan", [[42.50, 0.80, 42.65, 1.10]], {alias: ["Aiguestortes", "Aigüestortes i Estany de Sant Maurici", "Sant Maurici", "Espot", "Boí"]});
  g("cadi", "Cadí-Moixeró", GEB, "pyr-katalan", [[42.20, 1.50, 42.40, 2.00]], {alias: ["Cadi-Moixero", "Cadí", "Moixeró", "Gósol", "Bagà"]});
  g("picos", "Picos de Europa", GEB, null, [[43.10, -5.20, 43.35, -4.50]], {alias: ["Picos", "Naranjo de Bulnes", "Covadonga", "Fuente Dé", "Cares"]});
  g("sierra-nevada", "Sierra Nevada", GEB, null, [[36.90, -3.55, 37.18, -2.70]], {alias: ["Mulhacén", "Mulhacen", "Veleta", "Alpujarras", "Capileira"]});
  g("gredos", "Sierra de Gredos", GEB, null, [[40.10, -5.55, 40.40, -4.85]], {alias: ["Gredos", "Almanzor", "Plataforma de Gredos", "Candeleda"]});
  g("guadarrama", "Sierra de Guadarrama", GEB, null, [[40.70, -4.25, 41.00, -3.70]], {alias: ["Guadarrama", "Peñalara", "Navacerrada", "La Pedriza", "Cercedilla"]});
  g("montserrat", "Montserrat", GEB, null, [[41.55, 1.75, 41.67, 1.92]], {alias: ["Montserrat-Gebirge", "Monistrol de Montserrat"]});
  g("montseny", "Montseny", GEB, null, [[41.70, 2.30, 41.90, 2.55]], {alias: ["Massís del Montseny", "Turó de l'Home", "Viladrau"]});
  g("cazorla", "Sierra de Cazorla", GEB, null, [[37.75, -3.10, 38.40, -2.45]], {alias: ["Cazorla", "Sierras de Cazorla, Segura y Las Villas", "Segura de la Sierra", "Cazorla Natural Park"]});
  g("sierra-nieves", "Sierra de las Nieves", GEB, null, [[36.58, -5.10, 36.80, -4.85]], {alias: ["Sierra de las Nieves Nationalpark", "Parque Nacional Sierra de las Nieves", "Yunquera", "Tolox", "El Burgo", "Istán", "Parauta", "Torrecilla", "Málaga Hinterland"]});
  g("caminito", "Caminito del Rey", TAL, null, [[36.88, -4.85, 36.98, -4.70]], {alias: ["El Caminito del Rey", "Desfiladero de los Gaitanes", "El Chorro", "Ardales"]});
  g("cabo-de-gata", "Cabo de Gata", KUE, null, [[36.70, -2.30, 37.00, -1.85]], {alias: ["Cabo de Gata-Níjar", "Parque Natural Cabo de Gata", "San José", "Las Negras"]});
  g("grazalema", "Sierra de Grazalema", GEB, null, [[36.65, -5.50, 36.95, -5.20]], {alias: ["Grazalema", "Zahara de la Sierra", "Pinsapar"]});
  g("estrela", "Serra da Estrela", GEB, null, [[40.20, -7.80, 40.50, -7.35]], {alias: ["Estrela", "Manteigas", "Seia", "Covilhã"]});
  g("geres", "Peneda-Gerês", GEB, null, [[41.65, -8.45, 42.05, -7.90]], {alias: ["Peneda-Geres", "Gerês", "Geres", "Soajo", "Lamas de Mouro"]});
  g("algarve", "Algarve", KUE, null, [[36.95, -9.00, 37.40, -7.40]], {alias: ["Faro", "Lagos", "Sagres", "Monchique", "Tavira"]});
  g("rota-vicentina", "Rota Vicentina", KUE, null, [[37.00, -9.05, 37.90, -8.60]], {alias: ["Fischerpfad", "Trilho dos Pescadores", "Historischer Weg", "Porto Covo", "Zambujeira do Mar", "Odeceixe"]});

  /* ===================== Inseln ===================== */
  g("kanaren", "Kanaren", INS, null, [], {alias: ["Kanarische Inseln", "Islas Canarias", "Canarias", "Canary Islands", "Îles Canaries"]});
  g("la-gomera", "La Gomera", INS, "kanaren", [[28.00, -17.38, 28.24, -17.08]], {alias: ["Gomera", "Garajonay", "Valle Gran Rey", "Vallehermoso", "San Sebastián de la Gomera"]});
  g("teneriffa", "Teneriffa", INS, "kanaren", [[27.95, -16.95, 28.60, -16.10]], {alias: ["Tenerife", "Teneriffe"]});
  g("teide", "Teide", GEB, "teneriffa", [[28.15, -16.80, 28.35, -16.50]], {alias: ["Pico del Teide", "Teide-Nationalpark", "Las Cañadas", "Parque Nacional del Teide"]});
  g("teno", "Teno-Gebirge", GEB, "teneriffa", [[28.28, -16.92, 28.40, -16.75]], {alias: ["Teno", "Masca", "Macizo de Teno", "Los Gigantes"]});
  g("anaga", "Anaga", GEB, "teneriffa", [[28.48, -16.35, 28.58, -16.15]], {alias: ["Anaga-Gebirge", "Macizo de Anaga", "Taganana", "Chinamada"]});
  g("la-palma", "La Palma", INS, "kanaren", [[28.45, -18.02, 28.87, -17.70]], {alias: ["Isla Bonita", "Roque de los Muchachos", "Fuencaliente", "Santa Cruz de la Palma"]});
  g("caldera", "Caldera de Taburiente", GEB, "la-palma", [[28.68, -17.97, 28.80, -17.82]], {alias: ["Taburiente", "Caldera"]});
  g("gran-canaria", "Gran Canaria", INS, "kanaren", [[27.72, -15.85, 28.20, -15.33]], {alias: ["Grand Canary", "Roque Nublo", "Maspalomas", "Tejeda", "Las Palmas"]});
  g("el-hierro", "El Hierro", INS, "kanaren", [[27.62, -18.18, 27.88, -17.83]], {alias: ["Hierro"]});
  g("fuerteventura", "Fuerteventura", INS, "kanaren", [[28.04, -14.55, 28.76, -13.82]], {alias: ["Corralejo", "Morro Jable"]});
  g("lanzarote", "Lanzarote", INS, "kanaren", [[28.84, -13.90, 29.28, -13.40]], {alias: ["Timanfaya", "Teguise", "La Graciosa", "Playa Blanca"]});
  g("madeira-archipel", "Madeira-Archipel", INS, null, [], {alias: ["Madeira Islands", "Ilhas da Madeira"]});
  g("madeira", "Madeira", INS, "madeira-archipel", [[32.60, -17.30, 32.90, -16.65]], {alias: ["Funchal", "Pico Ruivo", "Levada", "Porto Moniz", "Pico do Arieiro"]});
  g("porto-santo", "Porto Santo", INS, "madeira-archipel", [[33.00, -16.45, 33.15, -16.25]], {alias: ["Ilha do Porto Santo"]});
  g("azoren", "Azoren", INS, null, [], {alias: ["Açores", "Acores", "Azores"]});
  g("sao-miguel", "São Miguel", INS, "azoren", [[37.68, -25.90, 37.93, -25.12]], {alias: ["Sao Miguel", "Ponta Delgada", "Sete Cidades", "Furnas", "Lagoa do Fogo"]});
  g("pico", "Pico", INS, "azoren", [[38.35, -28.55, 38.58, -28.00]], {alias: ["Ilha do Pico", "Montanha do Pico", "Madalena"]});
  g("faial", "Faial", INS, "azoren", [[38.50, -28.85, 38.67, -28.58]], {alias: ["Fayal", "Horta", "Capelinhos"]});
  g("sao-jorge", "São Jorge", INS, "azoren", [[38.60, -28.40, 38.78, -27.70]], {alias: ["Sao Jorge", "Velas", "Fajã"]});
  g("terceira", "Terceira", INS, "azoren", [[38.60, -27.40, 38.82, -26.98]], {alias: ["Angra do Heroísmo", "Praia da Vitória"]});
  g("graciosa", "Graciosa", INS, "azoren", [[39.00, -28.10, 39.12, -27.90]], {alias: ["Santa Cruz da Graciosa"]});
  g("flores", "Flores", INS, "azoren", [[39.35, -31.35, 39.55, -31.10]], {alias: ["Ilha das Flores", "Santa Cruz das Flores"]});
  g("corvo", "Corvo", INS, "azoren", [[39.65, -31.15, 39.73, -31.08]], {alias: ["Ilha do Corvo", "Vila do Corvo"]});
  g("santa-maria", "Santa Maria", INS, "azoren", [[36.90, -25.20, 37.03, -25.00]], {alias: ["Ilha de Santa Maria", "Vila do Porto"]});
  g("balearen", "Balearen", INS, null, [], {alias: ["Islas Baleares", "Illes Balears", "Balearic Islands", "Baleares", "Baléares"]});
  g("mallorca", "Mallorca", INS, "balearen", [[39.25, 2.30, 39.97, 3.50]], {alias: ["Majorca", "Palma de Mallorca", "Formentor", "Cap de Formentor"]});
  g("tramuntana", "Serra de Tramuntana", GEB, "mallorca", [[39.58, 2.30, 39.95, 3.10]], {alias: ["Tramuntana", "Sierra de Tramuntana", "Sóller", "Valldemossa", "Deià", "Lluc", "Puig Major", "Pollença"]});
  g("menorca", "Menorca", INS, "balearen", [[39.80, 3.80, 40.10, 4.35]], {alias: ["Minorca", "Cami de Cavalls", "Ciutadella", "Maó"]});
  g("ibiza", "Ibiza", INS, "balearen", [[38.82, 1.20, 39.14, 1.65]], {alias: ["Eivissa", "Sant Antoni"]});
  g("formentera", "Formentera", INS, "balearen", [[38.62, 1.35, 38.82, 1.65]], {alias: ["La Mola"]});
  g("reunion", "La Réunion", INS, null, [[-21.40, 55.20, -20.85, 55.85]], {alias: ["Réunion", "La Reunion", "Reunion", "Ile de la Réunion", "Île de La Réunion", "Reunion Island"]});
  g("mafate", "Mafate", TAL, "reunion", [[-21.12, 55.34, -21.00, 55.47]], {alias: ["Cirque de Mafate", "Marla", "Grand Place", "La Nouvelle", "Roche Plate", "Aurère"]});
  g("cilaos", "Cilaos", TAL, "reunion", [[-21.19, 55.40, -21.11, 55.50]], {alias: ["Cirque de Cilaos", "Palmiste Rouge", "Bras Rouge"]});
  g("salazie", "Salazie", TAL, "reunion", [[-21.10, 55.49, -20.99, 55.60]], {alias: ["Cirque de Salazie", "Hell-Bourg", "Grand Îlet", "Trou de Fer"]});
  g("piton-neiges", "Piton des Neiges", GEB, "reunion", [[-21.12, 55.44, -21.07, 55.52]], {alias: ["Piton des Neiges Gipfel"]});
  g("piton-fournaise", "Piton de la Fournaise", GEB, "reunion", [[-21.32, 55.63, -21.18, 55.82]], {alias: ["Fournaise", "Vulkan Réunion", "Pas de Bellecombe", "Enclos Fouqué", "Dolomieu"]});
  g("maido", "Maïdo", GEB, "reunion", [[-21.09, 55.30, -21.02, 55.40]], {alias: ["Maido", "Le Maïdo", "Maïdo Pass"]});
  g("plaine-cafres", "Plaine des Cafres", REG, "reunion", [[-21.30, 55.50, -21.17, 55.62]], {alias: ["Plaine-des-Cafres", "Bourg-Murat", "Le Tampon"]});
  g("plaine-palmistes", "Plaine des Palmistes", REG, "reunion", [[-21.17, 55.60, -21.08, 55.70]], {alias: ["Plaine-des-Palmistes", "Bélouve"]});
  g("plaine-sables", "Plaine des Sables", REG, "reunion", [[-21.25, 55.55, -21.19, 55.66]], {alias: ["Plaine-des-Sables"]});
  g("sud-sauvage", "Sud Sauvage", KUE, "reunion", [[-21.42, 55.55, -21.30, 55.82]], {alias: ["wilde Südküste", "Südküste", "Saint-Joseph", "Saint-Philippe", "Grand Brûlé"]});
  g("ostkueste", "Ostküste", KUE, "reunion", [[-21.22, 55.62, -20.88, 55.85]], {alias: ["Ostkueste", "Saint-Benoît", "Sainte-Rose", "Bras-Panon"]});
  g("westkueste", "Westküste", KUE, "reunion", [[-21.31, 55.20, -20.93, 55.35]], {alias: ["Westkueste", "Saint-Gilles", "Saint-Paul", "Saint-Leu", "L'Étang-Salé"]});
  g("nordkueste", "Nordküste", KUE, "reunion", [[-20.95, 55.28, -20.85, 55.68]], {alias: ["Nordkueste", "Saint-Denis", "Sainte-Marie", "Sainte-Suzanne"]});
  g("korsika", "Korsika", INS, null, [[41.33, 8.53, 43.03, 9.57]], {alias: ["Corse", "Corsica", "GR 20", "GR20", "Calenzana", "Vizzavona"]});
  g("sardinien", "Sardinien", INS, null, [[38.85, 8.10, 41.30, 9.85]], {alias: ["Sardegna", "Sardinia", "Cagliari", "Alghero"]});
  g("gennargentu", "Gennargentu", GEB, "sardinien", [[39.85, 9.05, 40.30, 9.60]], {alias: ["Punta La Marmora", "Fonni", "Desulo"]});
  g("supramonte", "Supramonte", GEB, "sardinien", [[40.05, 9.25, 40.40, 9.70]], {alias: ["Selvaggio Blu", "Cala Luna", "Oliena", "Orgosolo", "Cala Gonone", "Golfo di Orosei"]});
  g("sizilien", "Sizilien", INS, null, [[36.60, 12.40, 38.32, 15.70]], {alias: ["Sicilia", "Sicily", "Sicile"]});
  g("aetna", "Ätna", GEB, "sizilien", [[37.55, 14.80, 37.90, 15.20]], {alias: ["Aetna", "Etna", "Mount Etna", "Mongibello", "Nicolosi", "Linguaglossa"]});
  g("madonie", "Madonie", GEB, "sizilien", [[37.75, 13.85, 38.00, 14.30]], {alias: ["Piano Battaglia", "Castelbuono", "Isnello"]});
  g("nebrodi", "Nebrodi", GEB, "sizilien", [[37.80, 14.40, 38.12, 15.05]], {alias: ["Monti Nebrodi", "Parco dei Nebrodi", "Lago Biviere"]});
  g("zingaro", "Zingaro", KUE, "sizilien", [[38.05, 12.70, 38.22, 12.90]], {alias: ["Riserva dello Zingaro", "Scopello", "San Vito lo Capo"]});
  g("iblei", "Iblei", GEB, "sizilien", [[36.75, 14.60, 37.20, 15.15]], {alias: ["Monti Iblei", "Hybläische Berge", "Pantalica", "Cavagrande", "Noto", "Ragusa"]});
  g("egadische", "Egadische Inseln", INS, "sizilien", [[37.88, 12.00, 38.05, 12.42]], {alias: ["Egadi", "Isole Egadi", "Aegadian Islands", "Favignana", "Levanzo", "Marettimo"]});
  g("aeolische", "Äolische Inseln", INS, "sizilien", [[38.35, 14.30, 38.82, 15.30]], {alias: ["Aeolische Inseln", "Liparische Inseln", "Isole Eolie", "Aeolian Islands", "Eolie", "Salina", "Panarea", "Filicudi", "Alicudi"]});
  g("stromboli", "Stromboli", INS, "aeolische", [[38.76, 15.18, 38.82, 15.26]], {alias: ["Strombolicchio"]});
  g("vulcano", "Vulcano", INS, "aeolische", [[38.35, 14.92, 38.435, 15.02]], {alias: ["Isola di Vulcano", "Gran Cratere"]});
  g("lipari", "Lipari", INS, "aeolische", [[38.435, 14.87, 38.55, 15.02]], {alias: ["Isola di Lipari"]});
  g("elba", "Elba", INS, null, [[42.72, 10.10, 42.88, 10.50]], {alias: ["Isola d'Elba", "Portoferraio", "Monte Capanne", "Toskanischer Archipel"]});
  g("kreta", "Kreta", INS, null, [[34.80, 23.45, 35.70, 26.35]], {alias: ["Crete", "Κρήτη", "Chania", "Heraklion", "Samaria", "Samariá", "Gavdos"]});
  /* 3.69.0 Peloponnes (Halbinsel, seit dem Kanal von Korinth formal eine Insel; Nordgrenze = Isthmus, ohne Attika und Mittelgriechenland) mit Messenien, Mani, Taygetos, Parnon, Arkadien, Argolis, Olympia/Elis.
     Vieleck, Näherung: die Küste ist grob, das Meer im Golf von Korinth und vor den Küsten ist mit eingeschlossen; die Inseln Hydra, Aigina, Kythira, Zakynthos gehören nicht dazu. */
  g("peloponnes", "Peloponnes", INS, null, [], {poly: [[[38.22, 21.28], [38.27, 21.60], [38.32, 21.82], [38.31, 22.10], [38.28, 22.45], [38.18, 22.80], [38.05, 22.97], [37.97, 23.04], [37.88, 23.10], [37.70, 23.22], [37.66, 23.43], [37.55, 23.45],
                                                    [37.45, 23.55], [37.40, 23.42], [37.33, 23.30], [37.22, 23.22], [37.00, 23.15], [36.70, 23.14], [36.42, 23.22], [36.30, 22.42], [36.50, 22.10], [36.62, 21.82], [36.82, 21.58], [37.25, 21.52],
                                                    [37.65, 21.15], [37.90, 21.02], [38.00, 21.05]]],
                                 alias: ["Peloponnese", "Peloponnesos", "Peloponnesus", "Morea", "Πελοπόννησος", "Péloponnèse", "Peloponeso"], anz: true});
  g("messenien", "Messenien", REG, "peloponnes", [[36.75, 21.62, 37.32, 22.28]], {alias: ["Messinia", "Messenia", "Μεσσηνία", "Kalamata", "Pylos", "Methoni", "Koroni", "Messini", "Kyparissia", "Ithomi", "Ithome", "Mavromati", "Antikes Messene", "Ancient Messene", "Voidokilia"], anz: true});
  g("mani", "Mani", KUE, "peloponnes", [[36.36, 22.20, 36.90, 22.60]], {alias: ["Μάνη", "Innere Mani", "Äußere Mani", "Areopoli", "Stoupa", "Kardamyli", "Gytheio", "Vathia", "Kap Tenaro", "Cape Tainaron", "Cape Matapan", "Limeni", "Itilo"]});
  g("taygetos", "Taygetos", GEB, "peloponnes", [[36.85, 22.23, 37.12, 22.45]], {alias: ["Taygetus", "Taÿgetos", "Taigetos", "Ταΰγετος", "Profitis Ilias", "Mystras", "Mistras", "Sparta", "Taygetos-Gebirge"]});
  g("parnon", "Parnon", GEB, "peloponnes", [[37.00, 22.52, 37.35, 22.80]], {alias: ["Parnonas", "Parnon-Gebirge", "Πάρνωνας", "Kosmas", "Kastanitsa", "Megali Tourla"]});
  g("arkadien", "Arkadien", REG, "peloponnes", [[37.30, 22.00, 37.80, 22.60]], {alias: ["Arcadia", "Arkadia", "Αρκαδία", "Tripoli", "Tripolis", "Megalopoli", "Dimitsana", "Stemnitsa", "Vytina", "Tegea", "Lousios", "Lousios-Schlucht", "Mantineia"], anz: true});
  g("argolis", "Argolis", REG, "peloponnes", [[37.30, 22.55, 37.75, 23.42]], {alias: ["Argolida", "Argolid", "Argolis Peloponnes", "Αργολίδα", "Nafplio", "Nauplia", "Nauplion", "Argos", "Epidavros", "Epidaurus", "Mykene", "Mycenae", "Tiryns", "Ermioni", "Kranidi", "Methana", "Astros"], anz: true});
  g("ilia", "Olympia und Elis", REG, "peloponnes", [[37.42, 21.05, 37.98, 21.95]], {alias: ["Ilia", "Elis", "Ileia", "Ηλεία", "Olympia", "Archaia Olympia", "Pyrgos", "Katakolo", "Zacharo", "Foloi", "Andritsaina", "Kyllini", "Epikouros"], anz: true});
  g("zypern", "Zypern", INS, null, [[34.55, 32.25, 35.72, 34.65]], {alias: ["Cyprus", "Kıbrıs", "Kypros", "Troodos", "Paphos", "Akamas"]});
  g("malta", "Malta", INS, null, [[35.78, 14.18, 36.10, 14.60]], {alias: ["Gozo", "Valletta", "Comino"]});
  g("rhodos", "Rhodos", INS, null, [[35.85, 27.70, 36.50, 28.30]], {alias: ["Rhodes", "Rodos", "Lindos", "Prasonisi"]});
  g("santorin", "Santorin", INS, null, [[36.33, 25.33, 36.50, 25.50]], {alias: ["Santorini", "Thira", "Fira", "Oia", "Imerovigli"]});
  g("island", "Island", INS, null, [[63.30, -24.60, 66.60, -13.40]], {alias: ["Iceland", "Ísland", "Islande"]});
  g("laugavegur", "Laugavegur und Landmannalaugar", GEB, "island", [[63.62, -19.65, 64.08, -18.95]], {alias: ["Laugavegur", "Landmannalaugar", "Hrafntinnusker", "Álftavatn", "Emstrur", "Fjallabak"]});
  g("thorsmoerk", "Þórsmörk", TAL, "island", [[63.64, -19.65, 63.72, -19.40]], {alias: ["Thorsmörk", "Thorsmork", "Þorsmörk", "Porsmork", "Húsadalur", "Fimmvörðuháls"]});
  g("lofoten", "Lofoten", INS, null, [[67.80, 12.80, 68.60, 15.20]], {alias: ["Lofoten Islands", "Lofotinseln", "Svolvær", "Reine", "Henningsvær", "Moskenesøya"]});
  g("kapverden", "Kapverden", INS, null, [[14.70, -25.40, 17.30, -22.60]], {alias: ["Kap Verde", "Cabo Verde", "Cape Verde", "Capo Verde"]});
  g("santo-antao", "Santo Antão", INS, "kapverden", [[16.95, -25.40, 17.22, -25.00]], {alias: ["Santo Antao", "Ribeira Grande"]});
  g("mauritius", "Mauritius", INS, null, [[-20.55, 57.30, -19.95, 57.85]], {alias: ["Maurice", "Le Morne", "Black River Gorges", "Port Louis"]});

  /* ===================== Italien ===================== */
  g("toskana", "Toskana", REG, null, [], {poly: [[[44.40, 9.85], [44.25, 10.30], [44.15, 10.70], [44.12, 11.30], [44.00, 11.70], [43.80, 12.00], [43.55, 12.25], [43.25, 12.10], [43.02, 12.05], [42.70, 11.85],
                                                    [42.38, 11.60], [42.30, 11.10], [42.55, 10.05], [43.55, 10.10], [44.00, 9.90]]], alias: ["Toscana", "Tuscany", "Toscane"]});
  g("chianti", "Chianti", REG, "toskana", [[43.40, 11.10, 43.65, 11.55]], {alias: ["Chianti Classico", "Greve in Chianti", "Radda in Chianti", "Gaiole in Chianti", "Castellina in Chianti"]});
  g("val-d-orcia", "Val d'Orcia", TAL, "toskana", [[42.88, 11.45, 43.15, 11.85]], {alias: ["Val d’Orcia", "Orcia", "Pienza", "Montalcino", "San Quirico d'Orcia", "Bagno Vignoni", "Radicofani"]});
  g("apuaner", "Apuaner Alpen", GEB, "toskana", [[43.95, 10.05, 44.20, 10.45]], {alias: ["Alpi Apuane", "Apuan Alps", "Pania della Croce", "Carrara", "Garfagnana"]});
  g("cinque-terre", "Cinque Terre", KUE, "ligurien", [[44.08, 9.62, 44.17, 9.78]], {alias: ["Monterosso", "Vernazza", "Corniglia", "Manarola", "Riomaggiore"]});
  g("ligurien", "Ligurien", REG, null, [], {poly: [[[43.78, 7.52], [44.05, 7.58], [44.20, 7.85], [44.35, 8.15], [44.55, 8.55], [44.60, 9.20], [44.45, 9.75], [44.30, 10.05], [44.05, 10.05], [43.70, 9.50], [43.65, 8.00]]],
                                     alias: ["Liguria", "Ligurie", "Riviera di Levante", "Riviera di Ponente", "Genua", "Genova"]});
  g("umbrien", "Umbrien", REG, null, [[42.50, 12.00, 43.55, 13.05]], {alias: ["Umbria", "Perugia", "Assisi", "Spoleto", "Orvieto"]});
  g("marken", "Marken", REG, null, [], {poly: [[[43.95, 12.55], [43.95, 12.95], [43.55, 13.65], [43.00, 13.95], [42.75, 13.90], [42.75, 13.30], [42.95, 13.05], [43.20, 12.80], [43.40, 12.50], [43.60, 12.40]]],
                                       alias: ["Marche", "Le Marche", "Conero", "Frasassi"]});
  g("sibillini", "Monti Sibillini", GEB, "marken", [[42.70, 13.05, 43.05, 13.45]], {alias: ["Sibillini", "Sibillinische Berge", "Monte Vettore", "Visso", "Castelluccio"]});
  g("abruzzen", "Abruzzen", REG, null, [], {poly: [[[42.92, 13.20], [42.90, 14.05], [42.45, 14.45], [42.00, 14.80], [41.85, 14.75], [41.80, 14.20], [41.75, 13.85], [41.90, 13.60], [41.95, 13.30], [42.25, 13.10], [42.60, 13.15]]],
                                         alias: ["Abruzzo", "Abruzzi", "Abruzzes", "Pescasseroli"]});
  g("gransasso", "Gran Sasso", GEB, "abruzzen", [[42.35, 13.35, 42.60, 13.80]], {alias: ["Gran Sasso d'Italia", "Campo Imperatore", "Corno Grande", "Assergi"]});
  g("majella", "Majella", GEB, "abruzzen", [[41.90, 13.90, 42.25, 14.30]], {alias: ["Maiella", "Monte Amaro", "Sulmona", "Passo Lanciano", "Caramanico Terme"]});
  g("latium", "Latium", REG, null, [], {poly: [[[42.60, 11.75], [42.70, 12.35], [42.65, 13.30], [42.25, 13.20], [41.90, 13.50], [41.75, 13.85], [41.50, 13.85], [41.25, 13.80], [41.10, 13.55], [41.15, 13.20], [40.85, 12.90],
                                                  [41.50, 12.00], [42.00, 11.75], [42.40, 11.45]]], alias: ["Lazio", "Roma", "Circeo", "Ponza"]});
  g("kampanien", "Kampanien", REG, null, [], {poly: [[[41.30, 13.95], [41.50, 14.35], [41.40, 14.95], [41.15, 15.20], [40.75, 15.60], [40.45, 15.75], [40.10, 15.70], [39.95, 15.25], [40.40, 14.70],
                                                       [40.55, 14.10], [40.80, 13.80], [41.05, 13.90]]], alias: ["Campania", "Neapel", "Napoli", "Capri", "Ischia"]});
  g("amalfi", "Amalfiküste", KUE, "kampanien", [[40.55, 14.30, 40.72, 14.80]], {alias: ["Amalfikueste", "Costiera Amalfitana", "Amalfi Coast", "Amalfi", "Positano", "Ravello", "Sorrent", "Sorrento", "Sentiero degli Dei"]});
  g("cilento", "Cilento", GEB, "kampanien", [[39.95, 14.85, 40.45, 15.70]], {alias: ["Cilento-Nationalpark", "Parco Nazionale del Cilento", "Paestum", "Palinuro", "Agropoli", "Sapri"]});
  g("vesuv", "Vesuv", GEB, "kampanien", [[40.77, 14.33, 40.88, 14.50]], {alias: ["Vesuvio", "Vesuvius", "Ercolano"]});
  g("apulien", "Apulien", REG, null, [], {poly: [[[41.95, 15.15], [42.00, 16.10], [41.55, 16.10], [41.10, 17.00], [40.70, 18.05], [40.15, 18.55], [39.78, 18.40], [39.90, 17.95], [40.40, 17.25], [40.50, 17.00],
                                                   [40.80, 16.55], [41.15, 15.75], [41.50, 15.10]]], alias: ["Puglia", "Apulia", "Pouilles", "Bari", "Lecce"]});
  g("gargano", "Gargano", GEB, "apulien", [[41.60, 15.55, 42.00, 16.25]], {alias: ["Promontorio del Gargano", "Vieste", "Monte Sant'Angelo", "Peschici", "Foresta Umbra"]});
  g("salento", "Salento", KUE, "apulien", [[39.78, 17.75, 40.50, 18.55]], {alias: ["Lecce", "Otranto", "Gallipoli", "Santa Maria di Leuca"]});
  g("basilikata", "Basilikata", REG, null, [], {poly: [[[41.05, 15.60], [40.85, 16.20], [40.65, 16.75], [40.40, 16.90], [40.10, 16.65], [39.95, 16.20], [39.90, 15.70], [40.05, 15.60], [40.30, 15.70],
                                                         [40.55, 15.60], [40.85, 15.40]]], alias: ["Basilicata", "Lukanien", "Matera", "Potenza", "Maratea"]});
  g("kalabrien", "Kalabrien", REG, null, [], {poly: [[[40.05, 15.75], [40.05, 16.55], [39.75, 16.95], [39.40, 17.20], [39.00, 17.20], [38.40, 16.70], [37.90, 16.15], [37.90, 15.65], [38.40, 15.60],
                                                       [38.80, 15.80], [39.20, 15.90], [39.60, 15.75]]], alias: ["Calabria", "Calabre", "Tropea", "Cosenza"]});
  g("pollino", "Pollino", GEB, "kalabrien", [[39.80, 15.95, 40.00, 16.45]], {alias: ["Pollino-Nationalpark", "Parco Nazionale del Pollino", "Serra Dolcedorme", "Rotonda", "Civita"]});
  g("aspromonte", "Aspromonte", GEB, "kalabrien", [[37.95, 15.70, 38.30, 16.10]], {alias: ["Parco Nazionale dell'Aspromonte", "Gambarie", "Montalto"]});
  g("sila", "Sila", GEB, "kalabrien", [[39.10, 16.30, 39.45, 16.80]], {alias: ["Sila Grande", "Parco Nazionale della Sila", "Camigliatello Silano", "Lorica"]});

  /* ===================== Küsten und Inseln Deutschlands; weitere Küsten ===================== */
  g("ruegen", "Rügen", INS, null, [[54.25, 13.20, 54.70, 13.80]], {alias: ["Ruegen", "Kap Arkona", "Binz", "Sassnitz", "Putbus"]});
  g("jasmund", "Jasmund", KUE, "ruegen", [[54.50, 13.50, 54.62, 13.70]], {alias: ["Königsstuhl", "Nationalpark Jasmund", "Kreideküste", "Sassnitz"]});
  g("moenchgut", "Mönchgut", KUE, "ruegen", [[54.25, 13.60, 54.40, 13.80]], {alias: ["Moenchgut", "Göhren", "Thiessow", "Sellin"]});
  g("hiddensee", "Hiddensee", INS, null, [[54.50, 13.05, 54.62, 13.17]], {alias: ["Insel Hiddensee", "Vitte", "Neuendorf"]});
  g("usedom", "Usedom", INS, null, [[53.85, 13.75, 54.17, 14.30]], {alias: ["Uznam", "Heringsdorf", "Zinnowitz", "Ahlbeck", "Peenemünde", "Świnoujście"]});
  g("darss", "Fischland-Darß-Zingst", KUE, null, [[54.33, 12.30, 54.50, 12.90]], {alias: ["Fischland-Darss-Zingst", "Darß", "Darss", "Fischland", "Zingst", "Prerow", "Ahrenshoop", "Darßer Ort", "Wustrow"]});
  g("nordfriesische", "Nordfriesische Inseln", INS, null, [[54.45, 8.25, 55.06, 8.92]], {alias: ["Nordfriesland", "Halligen", "North Frisian Islands", "Pellworm", "Nordstrand", "Hallig Hooge"]});
  g("sylt", "Sylt", INS, "nordfriesische", [[54.74, 8.25, 55.06, 8.47]], {alias: ["Westerland", "Kampen", "Hörnum"]});
  g("amrum", "Amrum", INS, "nordfriesische", [[54.60, 8.28, 54.72, 8.45]], {alias: ["Wittdün", "Norddorf"]});
  g("foehr", "Föhr", INS, "nordfriesische", [[54.66, 8.45, 54.76, 8.65]], {alias: ["Foehr", "Wyk auf Föhr"]});
  g("ostfriesische", "Ostfriesische Inseln", INS, null, [[53.52, 6.58, 53.62, 6.78], [53.66, 6.90, 53.70, 7.10], [53.69, 7.05, 53.74, 7.25], [53.71, 7.33, 53.74, 7.45], [53.73, 7.45, 53.77, 7.60],
                                                           [53.75, 7.65, 53.78, 7.80], [53.77, 7.83, 53.80, 8.00]],
    {alias: ["East Frisian Islands", "Borkum", "Juist", "Norderney", "Baltrum", "Langeoog", "Spiekeroog", "Wangerooge"]});
  g("helgoland", "Helgoland", INS, null, [[54.15, 7.84, 54.22, 7.95]], {alias: ["Heligoland", "Düne", "Duene"]});
  g("normandie", "Normandie", REG, null, [], {poly: [[[48.55, -1.80], [49.75, -2.00], [49.75, -1.25], [49.40, -1.00], [49.40, 0.00], [49.78, 0.10], [50.10, 1.40], [49.70, 1.85], [49.30, 1.80], [48.80, 1.55], [48.50, 0.90],
                                                       [48.30, 0.00], [48.40, -0.90]]], alias: ["Normandy", "Normandie (Frankreich)", "Mont-Saint-Michel", "Étretat", "Omaha Beach", "Cotentin"]});
  g("bretagne", "Bretagne", REG, null, [], {poly: [[[48.80, -5.20], [48.90, -3.90], [48.75, -2.30], [48.66, -1.95], [48.55, -1.55], [48.20, -1.20], [47.85, -1.05], [47.45, -1.80], [47.35, -2.50],
                                                      [47.45, -3.30], [47.70, -4.20], [47.85, -4.50], [48.30, -5.20]]], alias: ["Brittany", "Bretagne (Frankreich)", "Finistère", "Côtes-d'Armor", "Morbihan"]});
  g("calanques", "Calanques", KUE, null, [[43.15, 5.30, 43.27, 5.62]], {alias: ["Calanques de Marseille", "Parc national des Calanques", "Cassis", "Sormiou", "En-Vau", "Luminy"]});
  g("cornwall", "Cornwall", KUE, null, [[49.90, -5.80, 50.92, -4.15]], {alias: ["South West Coast Path", "Kernow", "Land's End", "Lizard", "St Ives", "Newquay", "Padstow", "Tintagel"]});
  g("pembrokeshire", "Pembrokeshire", KUE, null, [[51.60, -5.35, 52.10, -4.65]], {alias: ["Pembrokeshire Coast Path", "Sir Benfro", "St Davids", "Tenby", "Fishguard"]});
  g("dalmatien", "Dalmatien", KUE, null, [], {poly: [[[44.40, 15.20], [44.25, 15.90], [43.70, 16.70], [43.40, 17.30], [43.05, 17.75], [42.60, 18.40], [42.40, 18.45], [42.55, 18.00], [42.90, 17.10],
                                                      [43.10, 16.30], [43.60, 15.70], [44.00, 15.00]]], alias: ["Dalmacija", "Dalmatia", "Dalmatie", "Split", "Dubrovnik", "Zadar", "Makarska", "Hvar", "Brač"], anz: true});
  g("istrien", "Istrien", KUE, null, [[44.75, 13.45, 45.55, 14.22]], {alias: ["Istra", "Istria", "Istrie", "Pula", "Rovinj", "Poreč", "Učka", "Motovun"], anz: true});
  g("kvarner", "Kvarner", KUE, null, [[44.45, 14.20, 45.40, 15.00]], {alias: ["Kvarner Bucht", "Kvarner Bay", "Rijeka", "Opatija", "Krk", "Cres", "Lošinj", "Rab", "Velebit"], anz: true});
  g("lykien", "Lykischer Weg", KUE, null, [[36.15, 29.00, 36.70, 30.60]], {alias: ["Lykien", "Lycian Way", "Likya Yolu", "Fethiye", "Ölüdeniz", "Kaş", "Kalkan", "Olympos", "Çıralı"]});
  g("skandinavien", "Skandinavien", GEB, null, [], {alias: ["Scandinavia", "Skandinavia"]});
  g("jotunheimen", "Jotunheimen", GEB, "skandinavien", [[61.30, 7.70, 61.90, 9.00]], {alias: ["Jotunheimen Nationalpark", "Besseggen", "Galdhøpiggen", "Gjendesheim", "Spiterstulen"]});
  g("hardangervidda", "Hardangervidda", GEB, "skandinavien", [[59.80, 6.90, 60.70, 8.60]], {alias: ["Hardangervidda Nationalpark", "Hardanger", "Finse", "Haukeliseter", "Vøringsfossen"]});
  g("lyngen", "Lyngen", GEB, "skandinavien", [[69.35, 19.90, 70.10, 20.80]], {alias: ["Lyngenalpen", "Lyngen Alps", "Lyngsalpene", "Lyngseidet", "Skibotn"]});
  g("rondane", "Rondane", GEB, "skandinavien", [[61.70, 9.60, 62.05, 10.40]], {alias: ["Rondane Nationalpark", "Rondslottet", "Rondvassbu"]});
  g("lappland", "Lappland", REG, "skandinavien", [[65.80, 17.60, 68.50, 24.20], [66.00, 24.20, 69.10, 29.80], [68.50, 20.40, 69.10, 24.20]], {alias: ["Lapland", "Lappi", "Sápmi", "Norrbotten"], anz: true});
  g("kebnekaise", "Kebnekaise", GEB, "lappland", [[67.75, 18.20, 68.05, 19.20]], {alias: ["Kungsleden", "Nikkaluokta", "Kebnekaise Fjällstation", "Tarfala"]});
  g("sarek", "Sarek", GEB, "lappland", [[67.10, 16.60, 67.60, 18.20]], {alias: ["Sarek Nationalpark", "Sarek National Park", "Rapadalen"]});
  g("abisko", "Abisko", GEB, "lappland", [[68.25, 18.40, 68.50, 19.30]], {alias: ["Abisko Nationalpark", "Kungsleden", "Abiskojaure", "Riksgränsen", "Nikkaluokta"]});
  g("rumaenische-karpaten", "Rumänische Karpaten", GEB, "karpaten", [[45.10, 22.20, 45.78, 26.10], [47.30, 24.20, 47.70, 25.00], [46.90, 25.80, 47.05, 26.05]],
    {alias: ["Rumaenische Karpaten", "Carpații Meridionali", "Südkarpaten", "Karpaten Rumänien", "Făgăraș", "Fagaras", "Bucegi", "Retezat", "Piatra Craiului", "Rodna", "Ceahlău", "Moldoveanu"]});
  g("rila", "Rila", GEB, null, [[41.95, 23.05, 42.30, 23.85]], {alias: ["Rila-Gebirge", "Rila Mountains", "Musala", "Rila-Kloster", "Siebenseen", "Borovets"]});
  g("pirin", "Pirin", GEB, null, [[41.50, 23.20, 41.95, 23.70]], {alias: ["Pirin-Gebirge", "Pirin Mountains", "Vihren", "Bansko", "Razlog"]});
  g("durmitor", "Durmitor", GEB, null, [[42.95, 18.80, 43.35, 19.35]], {alias: ["Durmitor Nationalpark", "Žabljak", "Zabljak", "Bobotov Kuk", "Crno Jezero"]});
  g("prokletije", "Prokletije", GEB, null, [[42.35, 19.60, 42.70, 20.20]], {alias: ["Albanische Alpen", "Accursed Mountains", "Bjeshkët e Nemuna", "Theth", "Valbona", "Plav", "Gusinje"]});

  /* ===================== Außereuropäisch (nur, was sicher ist) ===================== */
  g("hoher-atlas", "Hoher Atlas (Toubkal)", GEB, null, [[31.00, -8.10, 31.25, -7.70]], {alias: ["Hoher Atlas", "High Atlas", "Haut Atlas", "Toubkal", "Imlil"]});
  g("annapurna", "Annapurna", GEB, null, [[28.30, 83.55, 28.95, 84.40]], {alias: ["Annapurna Circuit", "Annapurna-Region", "Manang", "Thorong La", "Annapurna Base Camp"]});
  g("everest", "Everest-Region", GEB, null, [[27.65, 86.55, 28.10, 87.05]], {alias: ["Everest", "Khumbu", "Sagarmatha", "Lukla", "Namche Bazaar", "Everest Base Camp"]});
  g("kilimandscharo", "Kilimandscharo", GEB, null, [[-3.30, 37.10, -2.95, 37.65]], {alias: ["Kilimanjaro", "Kilimandjaro", "Marangu", "Machame", "Uhuru Peak"]});
  g("hawaii", "Hawaii", INS, null, [], {alias: ["Hawai'i", "Hawaiian Islands", "Hawaiʻi"]});
  g("hawaii-big", "Hawaii (Big Island)", INS, "hawaii", [[18.90, -156.10, 20.30, -154.80]], {alias: ["Big Island", "Mauna Kea", "Mauna Loa", "Kilauea", "Kona"]});
  g("maui", "Maui", INS, "hawaii", [[20.58, -156.70, 21.05, -155.95]], {alias: ["Haleakalā", "Haleakala", "Lahaina"]});
  g("oahu", "Oʻahu", INS, "hawaii", [[21.24, -158.30, 21.72, -157.64]], {alias: ["Oahu", "Honolulu", "Diamond Head"]});
  g("kauai", "Kauaʻi", INS, "hawaii", [[21.87, -159.80, 22.25, -159.28]], {alias: ["Kauai", "Nā Pali", "Na Pali", "Waimea Canyon"]});
  g("patagonien", "Patagonien", GEB, null, [], {alias: ["Patagonia", "Patagonie"]});
  g("torres-del-paine", "Torres del Paine", GEB, "patagonien", [[-51.30, -73.40, -50.70, -72.60]], {alias: ["Torres del Paine Nationalpark", "Paine", "W-Trek"]});
  g("fitz-roy", "Fitz Roy", GEB, "patagonien", [[-49.60, -73.40, -49.10, -72.60]], {alias: ["Cerro Fitz Roy", "El Chaltén", "El Chalten", "Cerro Torre", "Los Glaciares"]});
  g("neuseeland-nord", "Neuseeland (Nordinsel)", INS, "neuseeland", [[-41.80, 172.60, -34.30, 178.70]], {alias: ["North Island", "Nordinsel", "Tongariro", "Rotorua", "Auckland", "Wellington"]});
  g("neuseeland-sued", "Neuseeland (Südinsel)", INS, "neuseeland", [[-47.40, 166.30, -40.45, 174.40]], {alias: ["South Island", "Südinsel", "Suedinsel", "Milford Track", "Queenstown", "Aoraki", "Mount Cook", "Abel Tasman", "Fiordland"]});
  g("neuseeland", "Neuseeland", INS, null, [], {alias: ["New Zealand", "Aotearoa", "Nouvelle-Zélande", "Nueva Zelanda"]});

  /* ===================== 3.70.0 Abgleich mit dem Rother-Wanderführer-Katalog =====================
     Die Titel der Reihe „Rother Wanderführer“ zeigen, nach welchen Regionen Wanderer suchen. Fehlende Regionen sind hier als Gebiete ergänzt (nur wo die Grenzen als Rechteck sicher genug sind),
     Regionen, die sich mit einem Gebirge überschneiden (Genfersee/Jura, Münsterland/Teutoburger Wald, Baskenland/Pyrenäen, Devon/Cornwall, Vesterålen/Lofoten, Siegerland/Sauerland, Emmental/Jura, Seefeld/Karwendel, Gruyère/Berner Oberland, Dauphiné/Vercors und Écrins), haben `prio: -1`: in der Anzeige gewinnt das Gebirge.
     Abweichende Schreibweisen und Namen von Wegen („Westweg“, „Goldsteig“, „GR 20“) stehen als Alias bei den vorhandenen Gebieten (`plus`). Näherungen wie alle Gebiete.
     Südtiroler Unterregionen schneiden sich über `in` mit der Fläche von Südtirol (nur Provinz Bozen), Dolomiten-Täler haben die Dolomiten als Eltern; beide sind Typ Region ohne `anz`:
     sie werden gefunden und gefiltert, ändern aber die Anzeige der Regionszeile nicht („Südtirol“, „Dolomiten“ bleiben). */
  const plus = (id, ...alias) => {
    const x = L.find(k => k.id === id);
    if (!x) throw new Error("plus: unbekanntes Gebiet " + id);
    for (const a of alias) if (![x.name].concat(x.alias).some(o => o.toLowerCase() === a.toLowerCase())) x.alias.push(a);
  };

  /* --- Deutschland --- */
  g("muensterland", "Münsterland", REG, null, [[51.70, 6.85, 52.35, 8.05]], {alias: ["Muensterland", "Münsterländer Parklandschaft", "Baumberge", "Coesfeld", "Steinfurt", "Warendorf", "Borken", "Westmünsterland"], anz: true, prio: -1});
  g("oberlausitz", "Oberlausitz", REG, null, [[50.85, 14.05, 51.45, 15.04]], {alias: ["Lausitzer Bergland", "Zittauer Gebirge", "Bautzen", "Görlitz", "Zittau", "Oybin", "Lausitz", "Upper Lusatia"], anz: true});
  g("seenplatte", "Mecklenburgische Seenplatte", REG, null, [[53.20, 12.20, 53.70, 13.35]], {alias: ["Mecklenburger Seenplatte", "Müritz", "Müritz-Nationalpark", "Neustrelitz", "Mirow", "Waren (Müritz)", "Seenplatte"], anz: true});
  g("bergisches-land", "Bergisches Land", REG, null, [[50.90, 6.95, 51.30, 7.60]], {alias: ["Bergisches", "Wuppertal", "Solingen", "Remscheid", "Wipperfürth", "Müngsten", "Burg an der Wupper"], anz: true});
  g("siegerland", "Siegerland und Wittgenstein", REG, null, [[50.75, 7.75, 51.08, 8.60]], {alias: ["Siegerland", "Wittgenstein", "Siegen", "Bad Berleburg", "Rothaargebirge", "Rothaarsteig", "Erndtebrück", "Hilchenbach"], anz: true, prio: -1});
  g("isarwinkel", "Isarwinkel", REG, "alpen", [[47.58, 11.30, 47.82, 11.75]], {alias: ["Bad Tölz", "Lenggries", "Jachenau", "Kochel am See", "Walchensee", "Kochelsee", "Benediktbeuern", "Sylvensteinsee", "Tölzer Land"], anz: true});
  g("pfaffenwinkel", "Pfaffenwinkel", REG, null, [[47.68, 10.85, 47.95, 11.35]], {alias: ["Weilheim", "Peißenberg", "Peiting", "Murnau", "Wessobrunn", "Schongau", "Bad Bayersoien"], anz: true});
  g("kaiserstuhl", "Kaiserstuhl", GEB, null, [[48.03, 7.55, 48.15, 7.75]], {alias: ["Kaiserstuhl Baden", "Breisach", "Endingen", "Ihringen", "Vogtsburg", "Oberrotweil", "Bickensohl"]});
  g("elbtalaue", "Elbtalaue", REG, null, [[53.00, 10.60, 53.40, 11.70]], {alias: ["Wendland", "Hitzacker", "Dömitz", "Lenzen", "Lüchow-Dannenberg", "Niedersächsische Elbtalaue"], anz: true});
  g("uckermark", "Uckermark", REG, null, [[52.85, 13.35, 53.40, 14.28]], {alias: ["Prenzlau", "Schwedt", "Angermünde", "Templin", "Schorfheide", "Biosphärenreservat Schorfheide-Chorin"], anz: true});
  g("emsland", "Emsland und Grafschaft Bentheim", REG, null, [[52.36, 7.05, 53.15, 7.90]], {alias: ["Emsland", "Grafschaft Bentheim", "Meppen", "Lingen", "Papenburg", "Nordhorn", "Haselünne", "Hümmling"], anz: true});
  g("ostfriesland", "Ostfriesland", REG, null, [[53.20, 7.15, 53.62, 8.20]], {alias: ["Ostfriesland Küste", "Leer", "Emden", "Aurich", "Norden", "Wittmund", "Jever", "Wilhelmshaven", "Dollart"], anz: true});
  g("rheinhessen", "Rheinhessen", REG, null, [[49.65, 7.85, 50.00, 8.45]], {alias: ["Alzey", "Bingen am Rhein", "Ingelheim", "Rheinhessisches Hügelland", "Rheinterrasse", "Wonnegau"], anz: true});
  g("kraichgau", "Kraichgau", REG, null, [[48.95, 8.55, 49.30, 9.10]], {alias: ["Bruchsal", "Sinsheim", "Eppingen", "Bretten", "Heuchelberg", "Stromberg", "Zabergäu"], anz: true});
  g("taubertal", "Taubertal", TAL, null, [[49.35, 9.45, 49.80, 10.25]], {alias: ["Tauber", "Rothenburg ob der Tauber", "Bad Mergentheim", "Wertheim", "Tauberbischofsheim", "Lauda-Königshofen", "Liebliches Taubertal"]});
  g("altmuehltal", "Altmühltal", TAL, null, [[48.80, 10.85, 49.10, 11.95]], {alias: ["Altmuehltal", "Naturpark Altmühltal", "Altmühltal-Panoramaweg", "Eichstätt", "Kelheim", "Beilngries", "Treuchtlingen", "Solnhofen", "Riedenburg"]});
  g("saale-unstrut", "Saale-Unstrut", REG, null, [[51.05, 11.55, 51.30, 11.95]], {alias: ["Saale-Unstrut-Triasland", "Unstrut", "Naumburg", "Freyburg", "Bad Kösen", "Laucha", "Nebra"], anz: true});
  g("baederdreieck", "Niederbayerisches Bäderdreieck", REG, null, [[48.30, 12.85, 48.55, 13.45]], {alias: ["Bäderdreieck", "Rottal", "Bad Füssing", "Bad Griesbach", "Bad Birnbach", "Rottaler Bäderdreieck"], anz: true});
  g("bodensee", "Bodensee", REG, null, [[47.45, 8.85, 47.85, 9.80]], {alias: ["Lake Constance", "Lac de Constance", "Bodenseeregion", "Obersee", "Untersee", "Konstanz", "Friedrichshafen", "Überlingen", "Lindau", "Bregenz", "Meersburg", "Reichenau", "Mainau"], anz: true});

  /* --- Österreich --- */
  g("wienerwald", "Wienerwald", GEB, null, [[47.98, 15.85, 48.35, 16.35]], {alias: ["Wiener Wald", "Vienna Woods", "Wien und Wienerwald", "Biosphärenpark Wienerwald", "Kahlenberg", "Lainzer Tiergarten", "Baden bei Wien", "Mödling", "Klosterneuburg", "Purkersdorf", "Heiligenkreuz", "Hermannskogel"]});
  g("pitztal", "Pitztal", TAL, "alpen", [[46.88, 10.70, 47.27, 10.90]], {alias: ["Pitztaler Gletscher", "Imst", "Imst und Pitztal", "Jerzens", "Mittelberg im Pitztal", "St. Leonhard im Pitztal", "Rifflsee"]});
  g("lesachtal", "Lesachtal", TAL, "alpen", [[46.60, 12.78, 46.72, 13.05]], {alias: ["Lesach", "Kötschach-Mauthen", "Liesing", "St. Lorenzen im Lesachtal", "Maria Luggau", "Luggau"]});
  g("seefeld", "Seefeld und Leutasch", REG, "alpen", [[47.28, 11.07, 47.40, 11.25]], {alias: ["Seefelder Plateau", "Seefeld in Tirol", "Seefeld", "Leutasch", "Olympiaregion Seefeld", "Mösern", "Reith bei Seefeld"], anz: true, prio: -1});
  g("gastein", "Gasteinertal", TAL, "pongau", [[47.02, 13.03, 47.24, 13.17], [47.24, 13.09, 47.28, 13.17]], {alias: ["Gastein", "Bad Gastein", "Bad Hofgastein", "Dorfgastein", "Böckstein", "Sportgastein", "Gasteiner Tal", "Anlauftal"]});        // 3.70.1: Eltern Pongau (vorher Hohe Tauern), Westrand 13.03 (Rauris und Lend gehören nicht dazu), Ostrand 13.17 (Großarl/Hüttschlag nicht mehr)
  g("grossarltal", "Großarltal", TAL, "pongau", [[47.08, 13.17, 47.29, 13.28]], {alias: ["Großarl", "Grossarl", "Hüttschlag", "Huettschlag", "Großarler Tal", "Grossarler Tal", "Ellmautal", "Karseggalm", "Rattersberg"]});   // 3.70.1: neu; Kleinarl (13.30 E) gehört zu Kleinarl/Radstädter Tauern, nicht hierher
  g("mariazell", "Mariazeller Land", REG, "alpen", [[47.70, 15.15, 47.88, 15.52]], {alias: ["Mariazell", "Erlaufsee", "Gußwerk", "Mitterbach", "Mariazeller Bürgeralpe"], anz: true});
  g("moelltal", "Mölltal und Kreuzeckgruppe", TAL, "alpen", [[46.80, 12.90, 46.98, 13.40]], {alias: ["Mölltal", "Moelltal", "Kreuzeckgruppe", "Glockner-Region", "Winklern", "Obervellach", "Mallnitz", "Flattach", "Mölltaler Gletscher", "Reißeck"]});
  g("woerthersee", "Wörthersee", REG, null, [[46.58, 14.00, 46.68, 14.32]], {alias: ["Woerthersee", "Kärntner Seen", "Klagenfurt", "Velden am Wörthersee", "Pörtschach", "Maria Wörth"], anz: true});
  g("millstaettersee", "Millstätter See", REG, "alpen", [[46.72, 13.50, 46.85, 13.75]], {alias: ["Millstaetter See", "Kärntner Seen", "Millstatt", "Seeboden", "Döbriach", "Radenthein", "Millstätter Alpe"], anz: true});
  g("grazer-hausberge", "Grazer Hausberge", GEB, null, [[47.02, 15.28, 47.30, 15.55]], {alias: ["Graz", "Grazer Bergland", "Schöckl", "Plabutsch", "Gratkorn", "Gratwein", "Semriach"]});
  g("oststeiermark", "Oststeiermark", REG, null, [[46.88, 15.55, 47.50, 16.10]], {alias: ["Oststeirisches Hügelland", "Hartberg", "Fürstenfeld", "Weiz", "Feldbach", "Joglland", "Almenland", "Thermenland", "Pöllau", "Riegersburg", "Vorau"], anz: true});
  g("leithagebirge", "Leithagebirge und Rosaliengebirge", GEB, null, [[47.82, 16.42, 47.98, 16.80], [47.62, 16.22, 47.78, 16.45]], {alias: ["Leithagebirge", "Rosaliengebirge", "Rosalia", "Eisenstadt", "Hornstein", "Forchtenstein", "Mattersburg", "Kaisersteinbruch"]});
  g("kalkalpen", "Nationalpark Kalkalpen", GEB, "alpen", [[47.70, 14.20, 47.95, 14.60]], {alias: ["Kalkalpen", "Sengsengebirge", "Reichraminger Hintergebirge", "Windischgarsten", "Molln", "Hengstpass", "Steyrling"]});

  /* --- Schweiz --- */
  g("glarnerland", "Glarnerland", REG, "alpen", [[46.85, 8.88, 47.15, 9.25]], {alias: ["Glarus", "Kanton Glarus", "Glarner Alpen", "Elm", "Linthal", "Klöntal", "Braunwald", "Näfels", "Sardona", "Ostschweiz Glarnerland"], anz: true});
  g("zuerichsee", "Zürichsee und Zugerland", REG, null, [[47.05, 8.42, 47.38, 8.98]], {alias: ["Zuerichsee", "Zürichsee", "Zugerland", "Zugersee", "Rapperswil", "Albis", "Einsiedeln", "Pfannenstiel", "Zimmerberg", "Lake Zurich"], anz: true});
  g("genfersee", "Genfersee", REG, null, [[46.19, 6.15, 46.55, 7.00]], {alias: ["Lac Léman", "Lac Leman", "Léman", "Lake Geneva", "Genf", "Genève", "Lausanne", "Montreux", "Vevey", "Lavaux", "Évian", "Thonon", "Nyon", "Morges", "Chablais"], anz: true, prio: -1});
  g("vierwaldstaettersee", "Vierwaldstättersee", REG, "zentralschweiz", [[46.90, 8.20, 47.10, 8.70]], {alias: ["Vierwaldstaettersee", "Lake Lucerne", "Lac des Quatre-Cantons", "Weggis", "Vitznau", "Brunnen", "Flüelen", "Beckenried", "Küssnacht"], anz: true});
  g("emmental", "Emmental", REG, null, [[46.82, 7.55, 47.22, 8.15]], {alias: ["Emmental Oberaargau Entlebuch", "Entlebuch", "Oberaargau", "Napf", "Napfbergland", "Langnau im Emmental", "Burgdorf", "Sumiswald", "Biosphäre Entlebuch", "Escholzmatt", "Huttwil"], anz: true, prio: -1});
  g("gruyere", "Gruyère und Waadtländer Alpen", REG, "alpen", [[46.30, 6.98, 46.72, 7.35]], {alias: ["Gruyère", "Gruyere", "Greyerz", "Freiburger Alpen", "Freiburger Voralpen", "Waadtländer Alpen", "Alpes vaudoises", "Les Diablerets", "Diablerets", "Charmey", "Château-d'Oex", "Moléson", "Rossinière", "Les Mosses", "Leysin"], anz: true, prio: -1});
  g("surselva", "Surselva", REG, "graubuenden", [[46.52, 8.70, 46.85, 9.40]], {alias: ["Vorderrheintal", "Laax", "Flims", "Disentis", "Sedrun", "Ilanz", "Vals", "Valsertal", "Val Lumnezia", "Lugnez", "Obersaxen", "Oberalppass", "Ruinaulta", "Rheinschlucht"], anz: true});
  g("davos", "Davos und Prättigau", REG, "graubuenden", [[46.72, 9.70, 47.07, 9.97]], {alias: ["Davos", "Prättigau", "Praettigau", "Klosters", "Küblis", "Schiers", "Seewis", "Davos Klosters", "Parsenn", "Schatzalp", "Sertig", "Dischma"], anz: true});

  /* --- Italien --- */
  g("vinschgau", "Vinschgau", REG, "suedtirol", [[46.52, 10.45, 46.85, 10.98]], {in: "suedtirol", alias: ["Val Venosta", "Reschenpass", "Reschensee", "Schlanders", "Mals", "Latsch", "Naturns", "Glurns", "Prad am Stilfserjoch", "Graun im Vinschgau", "Kastelbell", "Schnalstal", "Schnals", "Kurzras", "Langtaufers", "Matsch"]});
  g("meran", "Meran und Umgebung", REG, "suedtirol", [[46.50, 10.98, 46.85, 11.30]], {in: "suedtirol", alias: ["Meran", "Merano", "Burggrafenamt", "Meraner Land", "Meraner Höhenweg", "Dorf Tirol", "Schenna", "Algund", "Lana", "Passeier", "Passeiertal", "St. Leonhard in Passeier", "Ultental", "Hafling", "Vöran", "Tisens"]});
  g("bozen", "Bozen und Überetsch", REG, "suedtirol", [[46.33, 11.15, 46.58, 11.50]], {in: "suedtirol", alias: ["Bozen", "Bolzano", "Überetsch", "Ueberetsch", "Bozner Unterland", "Kaltern", "Eppan", "Ritten", "Kalterer See", "Mendel", "Mendelpass", "Salten", "Terlan", "Jenesien", "Tramin", "Neumarkt", "Montiggler See", "Bozen und Kaltern"]});
  g("sterzing", "Sterzing und Wipptal", REG, "suedtirol", [[46.78, 11.30, 47.02, 11.65]], {in: "suedtirol", alias: ["Sterzing", "Vipiteno", "Wipptal", "Brenner", "Brennerpass", "Pfitsch", "Pfitscher Tal", "Ridnaun", "Ratschings", "Gossensaß", "Franzensfeste", "Jaufenpass"]});
  g("ahrntal", "Tauferer Ahrntal", REG, "suedtirol", [[46.85, 11.75, 47.12, 12.20]], {in: "suedtirol", alias: ["Ahrntal", "Tauferer Tal", "Sand in Taufers", "Taufers", "Rein in Taufers", "Prettau", "Kasern", "Steinhaus", "St. Johann im Ahrntal", "Campo Tures", "Valle Aurina", "Reintal", "Mühlwald"]});
  g("antholz", "Antholz und Gsies", REG, "suedtirol", [[46.75, 12.05, 46.95, 12.32]], {in: "suedtirol", alias: ["Antholz", "Anterselva", "Gsies", "Val Casies", "Rasen-Antholz", "Antholzer See", "Antholz Mittertal", "Antholz-Niedertal", "Gsieser Tal", "Welsberg"]});
  g("pustertal", "Pustertal", REG, "suedtirol", [[46.68, 11.70, 46.92, 12.30]], {in: "suedtirol", alias: ["Val Pusteria", "Bruneck", "Brunico", "Kronplatz", "Toblach", "Innichen", "Hochpustertal", "Olang", "Niederdorf", "Prags", "Pragser Wildsee", "St. Lorenzen", "Rodeneck"]});
  g("seiser-alm", "Seiser Alm", REG, "dolomiten", [[46.50, 11.50, 46.58, 11.66]], {alias: ["Alpe di Siusi", "Seis am Schlern", "Kastelruth", "Schlern", "Compatsch", "Völs am Schlern", "Santnerspitze", "Puflatsch", "Saltria"]});
  g("groeden", "Gröden", REG, "dolomiten", [[46.50, 11.66, 46.62, 11.80]], {alias: ["Grödnertal", "Val Gardena", "Gardena", "St. Ulrich", "Ortisei", "St. Christina", "Selva", "Wolkenstein", "Langkofel", "Sellajoch", "Seceda", "Raschötz", "Puez", "Dolomiten 1 Grödnertal"]});
  g("fassatal", "Fassatal", REG, "dolomiten", [[46.35, 11.64, 46.52, 11.85]], {alias: ["Val di Fassa", "Fassa", "Canazei", "Moena", "Vigo di Fassa", "Campitello", "Pordoijoch", "Passo Pordoi"]});
  g("gadertal", "Gadertal", REG, "dolomiten", [[46.50, 11.80, 46.78, 12.02]], {alias: ["Val Badia", "Alta Badia", "Abtei", "Corvara", "Kolfuschg", "St. Kassian", "San Cassiano", "La Villa", "Pedraces", "St. Vigil", "Enneberg", "Kronplatz", "Fanes", "Peitlerkofel"]});
  g("sextner", "Sextner Dolomiten", REG, "dolomiten", [[46.58, 12.15, 46.76, 12.45]], {alias: ["Sexten", "Sesto", "Drei Zinnen", "Tre Cime", "Innichen", "Toblach", "Dürrensee", "Misurina", "Auronzo"]});
  g("cortina", "Cortina d'Ampezzo", REG, "dolomiten", [[46.45, 11.98, 46.58, 12.25]], {alias: ["Cortina", "Ampezzo", "Ampezzaner Dolomiten", "Falzarego", "Passo Falzarego", "Cinque Torri", "Tofane", "Cristallo", "Passo Giau", "Dolomiten 6 Cortina"]});
  g("eggental", "Rosengarten und Latemar", REG, "dolomiten", [[46.33, 11.45, 46.50, 11.68]], {alias: ["Eggental", "Eggentaler Berge", "Val d'Ega", "Welschnofen", "Karersee", "Lago di Carezza", "Karerpass", "Deutschnofen", "Latemar", "Rosengarten", "Catinaccio", "Vajolet", "Nigerpass"]});
  g("lago-maggiore", "Lago Maggiore", REG, null, [[45.70, 8.34, 46.20, 8.95]], {alias: ["Langensee", "Lake Maggiore", "Lago d'Orta", "Ortasee", "Verbania", "Stresa", "Locarno", "Ascona", "Arona", "Luino", "Cannobio", "Brissago", "Borromäische Inseln", "Mottarone", "Pallanza", "Grand Tour Lago Maggiore"], anz: true});
  g("comer-see", "Comer See", REG, null, [[45.78, 9.05, 46.17, 9.45]], {alias: ["Lago di Como", "Lake Como", "Lario", "Como", "Lecco", "Bellagio", "Menaggio", "Varenna", "Colico", "Triangolo Lariano", "Grigna", "Grigne", "Cernobbio", "Tremezzina"], anz: true});
  g("adamello", "Adamello und Presanella", GEB, "alpen", [[46.02, 10.20, 46.30, 10.78]], {alias: ["Adamello", "Presanella", "Val Camonica", "Ponte di Legno", "Tonale", "Passo del Tonale", "Pinzolo", "Val di Genova", "Edolo", "Temù", "Val Rendena", "Carè Alto"]});
  g("vizentiner", "Vizentiner Alpen", GEB, "alpen", [[45.62, 11.15, 45.95, 11.65]], {alias: ["Vicentiner Alpen", "Prealpi Vicentine", "Vicentine Alps", "Asiago", "Altopiano di Asiago", "Sieben Gemeinden", "Sette Comuni", "Pasubio", "Pian delle Fugazze", "Recoaro Terme", "Kleine Dolomiten", "Piccole Dolomiti", "Lavarone", "Folgaria"]});
  g("golf-neapel", "Golf von Neapel", KUE, "kampanien", [[40.55, 13.85, 40.95, 14.45]], {alias: ["Bay of Naples", "Golfo di Napoli", "Pozzuoli", "Phlegräische Felder", "Campi Flegrei", "Procida", "Sorrent", "Sorrento", "Halbinsel Sorrent", "Penisola Sorrentina", "Monte Faito", "Castellammare di Stabia"]});

  /* --- Frankreich --- */
  g("burgund", "Burgund", REG, null, [[46.15, 2.85, 48.40, 5.50]], {alias: ["Bourgogne", "Burgundy", "Morvan", "Côte-d'Or", "Dijon", "Beaune", "Chablis", "Vézelay", "Cluny", "Auxerre", "Autun", "Nièvre", "Yonne", "Saône-et-Loire", "Bourgogne Loire Saône"], anz: true});
  g("dordogne", "Dordogne und Lot", REG, null, [[44.55, 0.00, 45.70, 1.50], [44.20, 1.00, 44.95, 2.20]], {alias: ["Dordogne", "Périgord", "Perigord", "Quercy", "Vézère", "Sarlat", "Rocamadour", "Les Eyzies", "Bergerac", "Cahors", "Périgueux", "Lot Frankreich", "Dordogne Lot"], anz: true});
  g("cote-d-azur", "Côte d'Azur", KUE, null, [[43.25, 6.45, 43.90, 7.55]], {alias: ["Cote d'Azur", "Französische Riviera", "French Riviera", "Riviera française", "Nizza", "Nice", "Cannes", "Antibes", "Saint-Tropez", "Menton", "Grasse", "Fréjus", "Esterel", "Massif de l'Esterel", "Cap Ferrat", "Côte d'Azur mit Calanques"], anz: true});
  g("dauphine", "Dauphiné", REG, null, [[44.20, 4.85, 45.55, 6.75]], {alias: ["Dauphine", "Dauphiné West", "Dauphiné Ost", "Isère", "Drôme", "Drôme provençale", "Hautes-Alpes", "Dévoluy", "Buëch", "Grenoble", "Gap", "Briançon"], anz: true, prio: -1});

  /* --- Spanien und Portugal --- */
  g("galicien", "Galicien", REG, null, [[41.95, -9.30, 43.05, -6.75], [43.05, -9.30, 43.80, -7.05]], {nicht: ["geres"], alias: ["Galicia", "Galiza", "Rías Baixas", "Rias Baixas", "Costa da Morte", "Finisterre", "Fisterra", "Santiago de Compostela", "Vigo", "A Coruña", "Lugo", "Ourense", "Pontevedra", "Ribeira Sacra", "Islas Cíes"], anz: true});
  g("kantabrien", "Kantabrien", REG, null, [[42.75, -4.85, 43.25, -3.15], [43.25, -4.58, 43.56, -3.15]], {alias: ["Cantabria", "Santander", "Liébana", "Potes", "Santillana del Mar", "Spanien Kantabrien"], anz: true});
  g("asturien", "Asturien", REG, null, [[42.95, -7.05, 43.25, -4.85], [43.25, -7.05, 43.67, -4.58]], {alias: ["Asturias", "Principado de Asturias", "Oviedo", "Gijón", "Covadonga", "Somiedo", "Ribadesella", "Cangas de Onís"], anz: true});
  g("baskenland", "Baskenland", REG, null, [[42.45, -3.45, 43.46, -1.72], [43.12, -1.80, 43.52, -0.95]], {alias: ["Euskadi", "País Vasco", "Pais Vasco", "Pays Basque", "Pays Basque Espagnol", "Bizkaia", "Gipuzkoa", "Álava", "San Sebastián", "Donostia", "Bilbao", "Biarritz", "Bayonne", "Saint-Jean-Pied-de-Port", "Baskenland Frankreich"], anz: true, prio: -1});
  g("costa-brava", "Costa Brava", KUE, null, [[41.65, 2.75, 42.45, 3.35]], {alias: ["Girona", "Gerona", "Roses", "Cadaqués", "Cap de Creus", "Palafrugell", "Tossa de Mar", "Lloret de Mar", "L'Estartit", "Begur", "Empordà", "Camí de Ronda", "Portbou", "Llançà", "Sant Feliu de Guíxols"], anz: true});
  g("costa-daurada", "Costa Daurada", KUE, null, [[40.55, 0.50, 41.30, 1.85]], {alias: ["Tarragona", "Salou", "Cambrils", "Prades", "Siurana", "Priorat", "Ebrodelta", "Delta de l'Ebre", "Montsant", "Sitges", "Vilanova i la Geltrú", "Reus", "L'Ametlla de Mar"], anz: true});
  g("costa-blanca", "Costa Blanca", KUE, null, [[37.95, -0.80, 38.88, 0.25]], {alias: ["Marina Alta", "Marina Baixa", "Alicante", "Alacant", "Benidorm", "Calpe", "Calp", "Dénia", "Denia", "Altea", "Jávea", "Xàbia", "Moraira", "Alcoy", "Alcoi", "Guadalest", "Puig Campana", "Peñón de Ifach", "Torrevieja", "Vall de Laguar"], anz: true});
  g("alentejo", "Alentejo", REG, null, [[37.50, -8.90, 39.30, -7.30]], {alias: ["Alto Alentejo", "Baixo Alentejo", "Évora", "Evora", "Beja", "Portalegre", "Sines", "Costa Alentejana", "Marvão", "Monsaraz", "Serra de São Mamede", "Mértola", "Vila Nova de Milfontes", "Odemira"], anz: true});
  g("nordportugal", "Nordportugal", REG, null, [[40.95, -8.90, 41.95, -6.55]], {alias: ["Portugal Norte", "Portugal Der Norden", "Minho", "Douro", "Alto Douro", "Dourotal", "Trás-os-Montes", "Tras-os-Montes", "Porto", "Braga", "Guimarães", "Viana do Castelo", "Vila Real", "Bragança", "Montesinho", "Serra do Marão"], anz: true});

  /* --- Griechenland --- */
  g("korfu", "Korfu", INS, null, [[39.37, 19.58, 39.82, 19.98]], {alias: ["Kerkyra", "Kerkira", "Corfu", "Κέρκυρα", "Paleokastritsa", "Pantokrator", "Kassiopi", "Sidari", "Lefkimmi", "Agios Gordios"]});
  g("chalkidiki", "Chalkidiki", KUE, null, [[39.90, 22.70, 40.55, 24.45]], {alias: ["Chalkidike", "Halkidiki", "Χαλκιδική", "Sithonia", "Kassandra", "Athos", "Berg Athos", "Nikiti", "Ouranoupoli", "Polygyros", "Arnaia"]});
  g("thassos", "Thassos", INS, null, [[40.57, 24.55, 40.80, 24.82]], {alias: ["Thasos", "Θάσος", "Limenas", "Skala Prinos", "Potos"]});
  g("olymp", "Olymp", GEB, null, [[39.98, 22.25, 40.20, 22.55]], {alias: ["Olymp Griechenland", "Mount Olympus", "Olympos", "Litochoro", "Mytikas", "Prionia", "Enipeas"]});
  g("pilion", "Pilion", GEB, null, [[39.08, 22.85, 39.50, 23.32]], {alias: ["Pelion", "Pilio", "Πήλιο", "Volos", "Zagora", "Tsagarada", "Makrinitsa", "Milies", "Portaria", "Damouchari", "Trikeri", "Argalasti"]});
  g("kefalonia", "Kefalonia", INS, null, [[38.05, 20.30, 38.30, 20.82], [38.30, 20.30, 38.50, 20.64]], {alias: ["Kefalinia", "Cephalonia", "Kefallonia", "Argostoli", "Fiskardo", "Lixouri", "Myrtos", "Berg Ainos", "Aenos"]});
  g("ithaka", "Ithaka", INS, null, [[38.30, 20.64, 38.50, 20.78]], {alias: ["Ithaki", "Ithaca", "Ιθάκη", "Vathy", "Stavros", "Frikes", "Kioni"]});
  g("zakynthos", "Zakynthos", INS, null, [[37.65, 20.60, 37.95, 21.05]], {alias: ["Zante", "Zakinthos", "Ζάκυνθος", "Navagio", "Shipwreck Beach", "Laganas", "Alykes", "Volimes"]});
  g("samos", "Samos", INS, null, [[37.64, 26.52, 37.86, 26.98]], {alias: ["Σάμος", "Pythagoreio", "Karlovasi", "Kokkari", "Mt Kerkis", "Kerkis", "Marathokambos"]});
  g("ikaria", "Ikaria", INS, null, [[37.54, 25.95, 37.70, 26.35]], {alias: ["Ikaría", "Nikaria", "Ικαρία", "Agios Kirykos", "Evdilos", "Armenistis"]});
  g("patmos", "Patmos", INS, null, [[37.27, 26.50, 37.38, 26.62]], {alias: ["Πάτμος", "Apokalypse-Höhle"]});
  g("fourni", "Fourni", INS, null, [[37.55, 26.40, 37.63, 26.55]], {alias: ["Fourni Korseon", "Φούρνοι", "Furni"]});

  /* --- Skandinavien und Nordsee/Ostsee --- */
  g("dovrefjell", "Dovrefjell", GEB, "skandinavien", [[62.15, 8.90, 62.55, 10.00]], {alias: ["Dovrefjell Nationalpark", "Dovre", "Snøhetta", "Snohetta", "Hjerkinn", "Kongsvoll", "Dombås", "Dombaas", "Moskusochsen"]});
  g("vesteraalen", "Vesterålen", INS, null, [[68.50, 14.40, 69.40, 16.30]], {alias: ["Vesteralen", "Lofoten und Vesterålen", "Andøya", "Andoya", "Hadsel", "Sortland", "Stokmarknes", "Melbu", "Langøya", "Hinnøya", "Øksnes"], prio: -1});
  g("gotland", "Gotland", INS, null, [[56.90, 18.05, 58.00, 19.40]], {alias: ["Fårö", "Faro Gotland", "Visby", "Fårösund", "Hoburgen", "Slite", "Ljugarn", "Gotland und Fårö"]});
  g("oeland", "Öland", INS, null, [[56.18, 16.42, 57.40, 17.10]], {alias: ["Oeland", "Borgholm", "Färjestaden", "Alvaret", "Stora Alvaret", "Ottenby", "Böda", "Byxelkrok", "Mörbylånga", "Grönhögen"]});
  g("bornholm", "Bornholm", INS, null, [[54.95, 14.62, 55.33, 15.20]], {alias: ["Rønne", "Ronne", "Svaneke", "Gudhjem", "Hammeren", "Hammershus", "Almindingen", "Christiansø", "Nexø", "Allinge", "Sandvig", "Dueodde"]});
  g("faeroeer", "Färöer", INS, null, [[61.35, -7.75, 62.45, -6.20]], {alias: ["Faeroeer", "Färöer-Inseln", "Faroe Islands", "Faroe", "Færøerne", "Føroyar", "Streymoy", "Eysturoy", "Vágar", "Mykines", "Tórshavn", "Gásadalur", "Saksun", "Kalsoy", "Suðuroy"]});
  g("kanalinseln", "Kanalinseln", INS, null, [[49.16, -2.28, 49.28, -2.00], [49.40, -2.70, 49.52, -2.30], [49.69, -2.25, 49.74, -2.15]], {alias: ["Channel Islands", "Îles Anglo-Normandes", "Jersey", "Guernsey", "Sark", "Herm", "Alderney", "Saint Helier", "Saint Peter Port"]});
  g("devon", "Devon", REG, null, [[50.20, -4.20, 50.90, -3.05], [50.90, -4.55, 51.25, -3.05]], {alias: ["Devon England", "Dartmoor", "Exmoor", "South Devon", "North Devon", "Torquay", "Plymouth", "Exeter", "Dartmouth", "Salcombe", "Ilfracombe", "Lynmouth", "Hartland", "Barnstaple", "Cornwall - Devon"], anz: true, prio: -1});

  /* --- Übersee --- */
  g("molokai", "Molokaʻi", INS, "hawaii", [[21.05, -157.32, 21.22, -156.72]], {alias: ["Molokai", "Kalaupapa", "Halawa"]});
  g("tasmanien", "Tasmanien", INS, null, [[-43.70, 144.55, -40.55, 148.45]], {alias: ["Tasmania", "Cradle Mountain", "Overland Track", "Freycinet", "Hobart", "Launceston", "Bay of Fires", "Tasmanische Halbinsel"]});

  /* --- Welle 2 (3.70.0): weitere Regionen des Katalogs, bewusst grob und innen (Rand zu Nachbarn und Meer ausgespart) --- */
  g("vancouver-island", "Vancouver Island", INS, null, [], {poly: [[[48.30, -123.65], [48.50, -123.40], [49.00, -123.65], [49.50, -124.25], [50.00, -125.05], [50.40, -125.90], [50.65, -127.00], [50.80, -127.95], [50.55, -127.70], [50.20, -127.30],
                                                                  [49.60, -126.60], [49.15, -126.10], [48.75, -125.20], [48.50, -124.55], [48.30, -124.00]]], alias: ["Vancouver-Insel", "Victoria BC", "Tofino", "Pacific Rim", "Nanaimo", "Strathcona", "West Coast Trail", "Campbell River"]});
  g("taiwan", "Taiwan", INS, null, [[21.90, 120.00, 25.35, 122.05]], {alias: ["Formosa", "Taipei", "Yushan", "Jadeberg", "Taroko", "Alishan", "Hualien", "Kaohsiung", "Sun Moon Lake"]});
  g("cordillera-blanca", "Cordillera Blanca", GEB, null, [[-10.20, -77.95, -8.50, -77.20]], {alias: ["Huaraz", "Huascarán", "Huascaran", "Santa-Cruz-Trek", "Santa Cruz Trek", "Llanganuco", "Peru Anden", "Callejón de Huaylas"]});
  g("cusco", "Cusco und Machu Picchu", REG, null, [[-14.00, -72.90, -12.90, -71.00]], {alias: ["Cusco", "Cuzco", "Machu Picchu", "Inkatrail", "Inka Trail", "Heiliges Tal", "Valle Sagrado", "Salkantay", "Ausangate", "Ollantaytambo", "Urubamba"], anz: true});
  g("westkap", "Westkap", REG, null, [[-34.85, 18.00, -31.00, 23.80]], {alias: ["Western Cape", "Südafrika West", "Kapstadt", "Cape Town", "Tafelberg", "Table Mountain", "Garden Route", "Cederberg", "Stellenbosch", "Kap der Guten Hoffnung", "Hermanus", "Franschhoek"], anz: true});
  g("sognefjord", "Sognefjord", KUE, "skandinavien", [[60.80, 5.00, 61.60, 7.60]], {alias: ["Sogn", "Flåm", "Flam", "Balestrand", "Gudvangen", "Fjærland", "Lærdal", "Aurlandsfjord", "Nærøyfjord", "Naeroyfjord", "Norwegen Süden Fjord"]});
  g("lysefjord", "Lysefjord und Preikestolen", KUE, "skandinavien", [[58.85, 5.95, 59.15, 6.75]], {alias: ["Preikestolen", "Prekestolen", "Kjerag", "Kjeragbolten", "Pulpit Rock", "Forsand", "Lysebotn", "Stavanger Umgebung"]});
  g("romsdal", "Romsdal und Sunnmøre", REG, "skandinavien", [[62.05, 6.05, 62.78, 8.00]], {alias: ["Romsdalen", "Sunnmøre", "Sunnmore", "Åndalsnes", "Andalsnes", "Trollstigen", "Trollveggen", "Geirangerfjord", "Geiranger", "Ålesund", "Molde", "Hjørundfjord", "Norwegen Mitte"], anz: true});
  g("andalusien", "Andalusien", REG, null, [], {poly: [[[36.00, -5.62], [36.00, -6.05], [36.40, -6.55], [37.05, -7.05], [37.15, -7.36], [37.50, -7.30], [37.90, -7.10], [38.00, -6.60], [38.05, -5.60], [38.15, -4.60], [38.30, -3.70],
                                                  [38.10, -3.00], [37.95, -2.50], [37.80, -2.15], [37.45, -1.80], [36.90, -1.80], [36.60, -2.30], [36.55, -3.10], [36.62, -4.50], [36.35, -5.15]]],
                                    alias: ["Andalucía", "Andalucia", "Andalusia", "Sevilla", "Córdoba", "Granada", "Málaga", "Cádiz", "Almería", "Jaén", "Huelva", "Ronda", "Costa del Sol", "Alpujarras", "Las Alpujarras", "Sierra de Aracena", "Doñana", "Andalusien Süd"], anz: true, prio: -1});
  g("provence", "Provence", REG, null, [[43.45, 5.00, 44.30, 6.40]], {alias: ["Haute-Provence", "Alpes-de-Haute-Provence", "Luberon", "Lubéron", "Verdon", "Gorges du Verdon", "Mont Ventoux", "Ventoux", "Sainte-Victoire", "Aix-en-Provence", "Alpilles", "Digne", "Provence Verdon"], anz: true, prio: -1});
  g("languedoc", "Languedoc-Roussillon", REG, null, [[42.55, 2.00, 43.75, 4.20]], {alias: ["Languedoc", "Roussillon", "Hérault", "Herault", "Aude", "Corbières", "Corbieres", "Montpellier", "Narbonne", "Carcassonne", "Perpignan", "Pyrénées-Orientales", "Katharerburgen", "Katharer", "Occitanie"], anz: true, prio: -1});
  g("elsass", "Elsass", REG, null, [], {poly: [[[49.02, 7.15], [49.02, 8.00], [48.88, 8.00], [48.58, 7.78], [48.00, 7.56], [47.60, 7.55], [47.58, 7.15], [47.85, 6.95], [48.30, 7.00], [48.70, 7.08]]],
                                    alias: ["Alsace", "Elsaß", "Route des Vins", "Weinstraße Elsass", "Sundgau", "Colmar", "Straßburg", "Strasbourg", "Mulhouse", "Mülhausen", "Haut-Rhin", "Bas-Rhin", "Rhin supérieur"], anz: true, prio: -1});
  g("veltlin", "Veltlin und Bergamasker Alpen", REG, "alpen", [[45.95, 9.45, 46.23, 10.30]], {alias: ["Valtellina", "Veltliner Tal", "Sondrio", "Tirano", "Morbegno", "Orobie", "Orobische Alpen", "Bergamasker Alpen", "Alpi Orobie", "Valmalenco"], anz: true});
  g("pindos", "Pindos", GEB, null, [[39.40, 20.65, 39.95, 21.40]], {alias: ["Pindosgebirge", "Pindus", "Πίνδος", "Zagori", "Zagoria", "Vikos", "Vikos-Schlucht", "Metsovo", "Ioannina", "Epirus", "Tymfi", "Astraka", "Papingo", "Pindos Zagori"]});
  g("yorkshire-dales", "Yorkshire Dales", GEB, null, [[54.05, -2.55, 54.45, -1.80]], {alias: ["Dales", "Yorkshire Dales Nationalpark", "Malham", "Hawes", "Settle", "Ingleborough", "Pen-y-ghent", "Wensleydale", "Swaledale", "Three Peaks", "Nordengland Dales"]});
  g("northumberland", "Northumberland", REG, null, [[55.00, -2.65, 55.45, -1.55]], {alias: ["Hadrian's Wall", "Hadrianswall", "Hadrian's Wall Path", "Northumberland Nationalpark", "Cheviot Hills", "Alnwick", "Bamburgh", "Housesteads", "Kielder", "Nordengland Küste"], anz: true});
  g("mittelrhein", "Oberes Mittelrheintal", TAL, null, [[49.98, 7.55, 50.38, 7.95]], {alias: ["Mittelrhein", "Mittelrheintal", "Rheinsteig", "RheinBurgenWeg", "Loreley", "Lorelei", "Boppard", "Bacharach", "Oberwesel", "St. Goar", "Rüdesheim", "Bingen am Rhein"], prio: -1});
  g("ries", "Nördlinger Ries", REG, null, [[48.78, 10.40, 48.98, 10.75]], {alias: ["Ries", "Rieskrater", "Nördlingen", "Noerdlinger Ries", "Riesrandweg", "Harburg", "Oettingen", "Bopfingen"], anz: true});
  g("fraenkisches-seenland", "Fränkisches Seenland", REG, null, [[49.05, 10.55, 49.20, 10.95]], {alias: ["Altmühlsee", "Brombachsee", "Igelsbachsee", "Gunzenhausen", "Pleinfeld", "Absberg", "Seenland Franken"], anz: true});
  g("waldviertel", "Waldviertel", REG, null, [[48.46, 14.95, 48.72, 15.75]], {alias: ["Waldviertel Niederösterreich", "Zwettl", "Horn", "Weitra", "Gmünd", "Ottenschlag", "Kamptal", "Kamp", "Ysper", "Yspertal"], anz: true});
  g("muehlviertel", "Mühlviertel", REG, null, [[48.42, 14.00, 48.58, 14.80]], {alias: ["Muehlviertel", "Freistadt", "Bad Leonfelden", "Rohrbach in Oberösterreich", "Sternstein", "Mühlkreis", "Granit- und Gneishochland", "Donau Böhmerwald"], anz: true});
  g("suedsteiermark", "Südsteiermark", REG, null, [[46.74, 15.30, 46.88, 15.75]], {alias: ["Steirisches Weinland", "Steirische Weinstraße", "Südsteirische Weinstraße", "Leibnitz", "Gamlitz", "Ehrenhausen", "Kitzeck", "Weinland Steiermark"], anz: true});
  g("flachgau", "Flachgau und Salzburger Umland", REG, null, [[47.76, 13.02, 47.97, 13.55]], {alias: ["Flachgau", "Rund um Salzburg", "Salzburger Seenland", "Mattsee", "Obertrum", "Seekirchen", "Wallersee", "Neumarkt am Wallersee", "Gaisberg", "Salzburg Umgebung", "Tennengau Flachgau"], anz: true, prio: -1});
  g("rupertiwinkel", "Rupertiwinkel", REG, null, [[47.80, 12.72, 48.08, 12.99]], {alias: ["Laufen", "Tittmoning", "Teisendorf", "Freilassing", "Waginger See", "Rund um Salzburg Rupertiwinkel", "Abtsdorfer See"], anz: true});
  g("liechtenstein", "Liechtenstein", REG, null, [[47.06, 9.50, 47.20, 9.63]], {alias: ["Fürstentum Liechtenstein", "Vaduz", "Malbun", "Triesenberg", "Schaan", "Bodensee bis Rätikon"], anz: true, prio: -1});

  /* --- Alias zu vorhandenen Gebieten (Schreibweisen, Wege, Titel der Reihe) --- */
  plus("allgaeu", "Oberallgäu", "Ostallgäu", "Westallgäu", "Unterallgäu", "Oberstaufen", "Allgäuer Alpenvorland", "Füssen", "Pfronten", "Immenstadt", "Sonthofen", "Bad Hindelang", "Allgäuer Höhenwege");
  plus("berchtesgaden", "Nationalpark Berchtesgaden", "Ramsau bei Berchtesgaden", "Schönau am Königssee");
  plus("schwarzwald", "Westweg", "Mittelweg", "Ostweg", "Fernwanderwege Schwarzwald");
  plus("lueneburger-heide", "Heidschnuckenweg", "Heidschnucken");
  plus("harz", "Harzer Hexenstieg", "Harzer-Hexen-Stieg", "Hexenstieg");
  plus("eifel", "Eifelsteig");
  plus("schwaebische-alb", "Albsteig", "Schwäbische Alb Ost", "Schwäbische Alb West");
  plus("bayerischer-wald", "Goldsteig");
  plus("oberpfaelzer-wald", "Goldsteig");
  plus("boehmerwald", "Tschechischer Goldsteig", "Goldsteig");
  plus("pfaelzerwald", "Deutsche Weinstraße", "Pfälzer Weinsteig", "Südliche Weinstraße", "Pfälzerwald und Deutsche Weinstraße");
  plus("moseltal", "Moselsteig");
  plus("frankenwald", "Coburger Land");
  plus("schladminger", "Steirische Niedere Tauern");
  plus("dachstein", "Dachstein-Tauern", "Dachstein Tauern West", "Dachstein Tauern Ost");
  plus("salzkammergut", "Salzkammergut West", "Salzkammergut Ost", "Bad Ischl", "Mondsee", "Fuschlsee", "Ausseerland", "Altaussee", "Gmunden", "Almtal");
  plus("hohetauern", "Hohe Tauern Nationalpark Nord", "Nationalpark Hohe Tauern Nord");
  plus("stubaital", "Wipptal", "Tiroler Wipptal", "Gschnitztal", "Sellraintal", "Sellrain", "Stubai-Wipptal", "Stubaier Höhenweg", "Sellrainer Hüttenrunde");
  plus("kaunertal", "Oberinntal", "Kaunertal Oberinntal");
  plus("ausserfern", "Lechweg", "Lechtaler Höhenweg");
  plus("wachau", "Welterbesteig Wachau", "Welterbesteig");
  plus("villach", "Kärntner Seen");
  plus("wetterstein", "Zugspitze mit Ammergauer Alpen");
  plus("wallis", "Oberwallis", "Unterwallis", "Walliser Alpen", "Goms", "Lötschental", "Tour Monte Rosa");
  plus("jura", "Schweizer Jura", "Französischer Jura", "Franche-Comté", "Jura Franche-Comté");
  plus("dolomiten", "Dolomiten Höhenwege", "Alta Via", "Dolomiten Fassatal", "Dolomiten Gadertal", "Dolomiten Sextner Dolomiten");
  plus("friaul", "Friuli Venezia Giulia", "Friaul-Julisch Venetien", "Julisch Venetien", "Friuli");
  plus("ligurien", "Italienische Riviera");
  plus("piemont", "Grande Traversata delle Alpi", "GTA");
  plus("calanques", "Côte d'Azur mit Nationalpark Calanques");
  plus("gardasee", "Gardaseeberge");
  plus("latium", "Rom", "Rom und Latium");
  plus("umbrien", "Franziskusweg", "Via di San Francesco");
  plus("korsika", "Mare e Monti", "Mare a Mare");
  plus("pyrenaeen", "GR 10", "GR 11", "Pyrenäen GR 10");
  plus("mallorca", "GR 221");
  plus("tramuntana", "GR 221", "Trockensteinroute", "Ruta de Pedra en Sec");
  plus("highlands", "West Highland Way");
  plus("lofoten", "Lofoten und Vesterålen");
  plus("hoher-atlas", "Marokko", "Morocco", "Maroc", "Atlas");

  /* ===================== Rechnen ===================== */
  const BY = {};
  L.forEach(x => { BY[x.id] = x; });
  const fold = s => String(s == null ? "" : s).toLowerCase().replace(/ß/g, "ss").replace(/[æ]/g, "ae").replace(/[œ]/g, "oe").replace(/[øð]/g, "o").replace(/[đ]/g, "d").replace(/[łŀ]/g, "l").replace(/ı/g, "i")
    .replace(/þ/g, "th").normalize("NFD").replace(/\p{M}/gu, "").replace(/[^a-z0-9]+/g, "");
  const kreis = s => fold(s).replace(/^(autonome)?(landkreis|bezirk|kreis|provinz|provincia|stadt|kreisfreie|region)(autonoma)?(di|von|de)?/, "");
  const okLL = (a, b) => typeof a === "number" && typeof b === "number" && isFinite(a) && isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180 && !(a === 0 && b === 0);
  const inBox = (b, la, ln) => la >= b[0] && la <= b[2] && ln >= b[1] && ln <= b[3];
  const inPoly = (ring, la, ln) => {                                   // Strahlverfahren (Rand zählt je nach Lage mal zu, mal nicht – genügt für Näherungen)
    let c = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [yi, xi] = ring[i], [yj, xj] = ring[j];
      if ((yi > la) !== (yj > la) && ln < ((xj - xi) * (la - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  // Hüllrechteck je Gebiet (Schnellprüfung) und Fläche (für „kleiner = spezifischer“)
  L.forEach(x => {
    const all = x.boxen.concat(x.poly.map(r => [Math.min(...r.map(p => p[0])), Math.min(...r.map(p => p[1])), Math.max(...r.map(p => p[0])), Math.max(...r.map(p => p[1]))]));
    x.hull = all.length ? [Math.min(...all.map(b => b[0])), Math.min(...all.map(b => b[1])), Math.max(...all.map(b => b[2])), Math.max(...all.map(b => b[3]))] : null;
    x.flaeche = all.reduce((s, b) => s + (b[2] - b[0]) * (b[3] - b[1]), 0) || 1e9;
    x.kreise = x.county.map(kreis);
    x.nkreise = x.nichtKreis.map(kreis);
    x.eigen = x.boxen.length > 0 || x.poly.length > 0 || x.county.length > 0;      // reine Oberbegriffe gelten nur über ihre Kinder
  });
  const tiefe = x => { let n = 0; for (let e = x.eltern && BY[x.eltern]; e && n < 10; e = e.eltern && BY[e.eltern]) n++; return n; };
  L.forEach(x => { x.tiefe = tiefe(x); });
  L.forEach(x => { x.quelle = "eingebaut"; });
  const NBASIS = L.length;                                                   // die eingebauten Gebiete stehen vorn; eigene (3.65.0) werden dahinter ersetzt (setEigene)

  /** Liegt die Koordinate in der Fläche des Gebiets (Rechtecke/Vielecke, ohne Bezirk, ohne Ausschluss)? */
  const flaeche = (x, la, ln) => !!x.hull && inBox(x.hull, la, ln) && (x.boxen.some(b => inBox(b, la, ln)) || x.poly.some(r => inPoly(r, la, ln)));
  const trifft = (x, la, ln, kr) => {
    if (kr && x.nkreise.includes(kr)) return false;                          // 3.68.0: der Bezirk der Tour liegt sicher nicht im Gebiet (Koordinaten am Rand täuschen sich leicht)
    let ok = false;
    if (la != null && x.hull) ok = flaeche(x, la, ln) && (!x.in || flaeche(BY[x.in], la, ln));
    if (!ok && kr && x.kreise.includes(kr)) ok = true;
    if (!ok) return false;
    return !x.nicht.some(n => (typeof n === "string" ? flaeche(BY[n], la, ln) && !(kr && BY[n].nkreise.includes(kr)) : la != null && inBox(n, la, ln)));      // Fläche des anderen Gebiets, außer sein Bezirk-Ausschluss (nichtKreis) greift: „Provinz Trient“ liegt nie in Südtirol
  };
  const cache = new Map();
  /** Gebiete einer Tour, spezifischste zuerst: [{id, name, typ, eltern}]. Mehrfachzuordnung gewollt; Eltern werden mitgeführt. Nur Koordinate (t.lat/t.lng), Bezirk als zusätzliche Möglichkeit. */
  const von = t => {
    if (!t) return [];
    const la = okLL(t.lat, t.lng) ? +t.lat : null, ln = la == null ? null : +t.lng, kr = t.g_county ? kreis(t.g_county) : "";
    const key = `${la}|${ln}|${kr}`;
    if (cache.has(key)) return cache.get(key);
    const ids = new Set();
    for (const x of L) if (x.eigen && trifft(x, la, ln, kr)) {
      ids.add(x.id);
      for (let e = x.eltern && BY[x.eltern], n = 0; e && n < 10; e = e.eltern && BY[e.eltern], n++) ids.add(e.id);
    }
    const out = [...ids].map(i => BY[i]).sort((a, b) => b.tiefe - a.tiefe || b.prio - a.prio || a.flaeche - b.flaeche || (a.id < b.id ? -1 : 1)).map(x => ({id: x.id, name: x.name, typ: x.typ, eltern: x.eltern}));
    if (cache.size > 20000) cache.clear();
    cache.set(key, out);
    return out;
  };
  /** Suchtext: Namen und Alias aller Gebiete der Tour (inklusive übergeordneter). */
  const namen = t => von(t).map(x => [x.name].concat(BY[x.id].alias).join(" ")).join(" ");
  /** Bundesland für die Suche: „Trentino-Südtirol“ zählt nicht als „Südtirol“ (die Provinz Bozen kommt über das Gebiet „Südtirol“). */
  const bundesland = t => {
    const s = t.g_state || "", f = fold(s);
    if (f.includes("trentino") && (f.includes("sudtirol") || f.includes("altoadige"))) return von(t).some(x => x.id === "suedtirol") ? "" : "Trentino";
    return s;
  };
  /** Gesamter Regionstext einer Tour für die Suche (Ort, Bezirk, Bundesland, Land, Gebiete). */
  const fuerSuche = t => `${t.g_place || ""} ${t.g_county || ""} ${bundesland(t)} ${t.g_country || ""} ${namen(t)}`;
  /** Das spezifischste anzeigbare Gebiet (Gebirge, Tal, Insel, Küste; Region nur mit anz) oder null; null auch, wenn es nur wiederholen würde, was Ort/Bundesland/Land schon sagen. */
  const anzeige = t => {
    const vs = von(t).filter(v => BY[v.id].typ !== REG || BY[v.id].anz);
    if (!vs.length) return null;
    const v = vs[0], x = BY[v.id], ns = [x.name].concat(x.alias).map(fold).filter(Boolean), nm = fold(x.name), pl = fold(t.g_place || "");
    // Bundesland, Land (der Bezirk steht nicht in der Zeile): Name oder Alias gleich = schon gesagt. Ort: nur der Name selbst (Alias nennen oft Orte des Gebiets: „Vallehermoso“ gehört zu La Gomera, ist aber nicht dasselbe)
    const gleich = [t.g_state, t.g_country].filter(Boolean).map(fold).some(o => ns.includes(o)) || (pl && (pl === nm || (nm.length >= 4 && pl.includes(nm))));
    return gleich ? null : v;                   // das spezifischste Gebiet sagt nichts Neues: lieber nichts als ein gröberes Gebiet
  };
  /** Teile der Regionszeile: Ort, Gebiet, Bundesland, Land (leere und doppelte entfallen) – für Tourseite und Tourblatt. */
  const regionTeile = t => regionMit(t).map(x => x.text);
  /** Wie regionTeile, jeder Teil als {text, gebiet}: gebiet = Kennung, wenn der Teil das Gebiet ist (für einen Link auf die Tourenliste dieses Gebiets), sonst null. */
  const regionMit = t => {
    const a = anzeige(t), out = [];
    for (const [s, g] of [[t.g_place, null], [a && a.name, a && a.id], [t.g_state, null], [t.g_country, null]]) if (s && !out.some(o => fold(o.text) === fold(s))) out.push({text: s, gebiet: g});
    return out;
  };
  /** Suchwörter zusammenfassen: aufeinanderfolgende Wörter, die zusammen den Namen oder Alias eines Gebiets ergeben („La Palma“, „Gran Canaria“, „Wilder Kaiser“), zählen als EIN Suchwort
   *  (sonst fände „Gran Canaria“ auch La Gomera: „Valle Gran Rey“ + „Islas Canarias“). Alle anderen Wörter bleiben einzeln. */
  const fold1 = s => String(s == null ? "" : s).toLowerCase().replace(/ß/g, "ss").replace(/[æ]/g, "ae").replace(/[œ]/g, "oe").replace(/[øð]/g, "o").replace(/[đ]/g, "d").replace(/[łŀ]/g, "l").replace(/þ/g, "th")
    .normalize("NFD").replace(/\p{M}/gu, "").replace(/[^a-z0-9]+/g, " ").trim();
  let PHR = null;
  const phrasen = toks => {
    if (!PHR) { PHR = new Set(); for (const x of L) for (const n of [x.name].concat(x.alias)) { const f = fold1(n); if (f.includes(" ")) PHR.add(f); } }
    const out = [];
    for (let i = 0; i < toks.length;) {
      let n = 0;
      for (let j = Math.min(toks.length, i + 6); j > i + 1; j--) if (PHR.has(fold1(toks.slice(i, j).join(" ")))) { n = j - i; break; }
      if (n) { out.push(toks.slice(i, i + n).join(" ")); i += n; } else out.push(toks[i++]);
    }
    return out;
  };
  /** Regionszeile als Text („Mauterndorf, Lungau, Salzburg, Österreich“), leer ohne Angaben. */
  const regionText = t => regionTeile(t).join(", ");
  /** Prüfbericht für Volker (im Browser: Gebiete.bericht(TOURS)): je Gebiet Anzahl und Beispiele, Touren in mehr als 3 Gebieten, Touren ohne Gebiet nach Land. Nur eine Funktion, keine Oberfläche. */
  const bericht = (touren, o = {}) => {
    const bsp = o.beispiele || 3, viele = o.viele || 3, je = {}, mehr = [], ohne = {};
    let mit = 0;
    for (const t of touren || []) {
      const vs = von(t);
      if (!vs.length) { const land = t.g_country || "(ohne Land)"; (ohne[land] ||= []).push(t); continue; }
      mit++;
      for (const v of vs) { const e = (je[v.id] ||= {id: v.id, name: v.name, typ: v.typ, n: 0, beispiele: []}); e.n++; if (e.beispiele.length < bsp) e.beispiele.push(t.name); }
      if (vs.length > viele) mehr.push({name: t.name, id: t.id, lat: t.lat, lng: t.lng, gebiete: vs.map(v => v.name)});
    }
    const gebiete = Object.values(je).sort((a, b) => b.n - a.n);
    const ohneLand = Object.entries(ohne).map(([land, ts]) => ({land, n: ts.length, beispiele: ts.slice(0, bsp).map(x => x.name)})).sort((a, b) => b.n - a.n);
    const leer = L.filter(x => x.eigen && !je[x.id]).map(x => x.name);
    const text = [`${(touren || []).length} Touren, davon ${mit} mit Gebiet, ${(touren || []).length - mit} ohne.`,
      "", "Gebiete (Touren):", ...gebiete.map(e => `  ${e.name} (${e.typ}): ${e.n} – z. B. ${e.beispiele.join("; ")}`),
      "", `Touren in mehr als ${viele} Gebieten: ${mehr.length}`, ...mehr.slice(0, 50).map(m => `  ${m.name} [${m.lat}, ${m.lng}]: ${m.gebiete.join(", ")}`),
      "", "Touren ohne Gebiet nach Land:", ...ohneLand.map(e => `  ${e.land}: ${e.n} – z. B. ${e.beispiele.join("; ")}`),
      "", `Gebiete ohne Tour: ${leer.length}`].join("\n");
    return {touren: (touren || []).length, mitGebiet: mit, gebiete, mehrfach: mehr, ohneGebiet: ohneLand, leer, text};
  };
  /** Konsistenzprüfung der Tabelle: Liste von Fehlern (leer = in Ordnung). */
  const pruefen = () => {
    const err = [], ids = new Set();
    for (const x of L) {
      if (ids.has(x.id)) err.push("doppelte id " + x.id);
      ids.add(x.id);
      if (!/^[a-z0-9-]+$/.test(x.id)) err.push("id ungültig " + x.id);
      if (![GEB, TAL, INS, KUE, REG].includes(x.typ)) err.push("typ ungültig " + x.id);
      if (!x.name) err.push("ohne name " + x.id);
      if (x.eltern && !BY[x.eltern]) err.push("eltern fehlt " + x.id + " → " + x.eltern);
      if (x.eltern === x.id) err.push("eltern = selbst " + x.id);
      if (x.in && !BY[x.in]) err.push("in fehlt " + x.id);
      const bs = x.boxen.concat(x.nicht.filter(n => Array.isArray(n)));
      for (const b of bs) {
        if (b.length !== 4 || b.some(v => typeof v !== "number" || !isFinite(v))) err.push("box ungültig " + x.id);
        else if (!(b[0] < b[2] && b[1] < b[3] && Math.abs(b[0]) <= 90 && Math.abs(b[2]) <= 90 && Math.abs(b[1]) <= 180 && Math.abs(b[3]) <= 180)) err.push("box lat0<lat1/lng0<lng1 verletzt " + x.id);
      }
      for (const r of x.poly) if (r.length < 3 || r.some(p => p.length !== 2 || Math.abs(p[0]) > 90 || Math.abs(p[1]) > 180)) err.push("poly ungültig " + x.id);
      for (const n of x.nicht) if (typeof n === "string" && !BY[n]) err.push("nicht fehlt " + x.id + " → " + n);
      if (!x.eigen && !L.some(k => k.eltern === x.id)) err.push("Oberbegriff ohne Kinder " + x.id);
      if (!x.eigen && x.typ === REG) err.push("Oberbegriff als region " + x.id);
    }
    for (const x of L) { let n = 0; for (let e = x; e && e.eltern; e = BY[e.eltern]) if (++n > 10) { err.push("Eltern-Kette zu lang/Schleife " + x.id); break; } }
    return err;
  };
  /** Eigene Gebiete (3.65.0, GET /api/gebiete/eigene: [{id, name, typ, box: [Süd, West, Nord, Ost], land}]): ersetzt die bisherigen eigenen. Ein eigenes Gebiet ist ein Rechteck ohne übergeordnetes Gebiet, Alias
   und Bezirk (wie app/gebiete.py `_eigen_zeile`) und geht bei der Anzeige und beim Reisenamen vor (Tiefe 99, wie eigene Reisen und eigene Namen Vorrang haben); es erscheint wie ein eingebautes in von(), Suche, Anzeige und Filter, mit quelle "eigen". */
  const setEigene = liste => {
    L.length = NBASIS;
    for (const k of Object.keys(BY)) if (BY[k].quelle === "eigen") delete BY[k];
    for (const e of Array.isArray(liste) ? liste : []) {
      const b = e && e.box, ok = Array.isArray(b) && b.length === 4 && b.every(v => typeof v === "number" && isFinite(v)) && b[0] < b[2] && b[1] < b[3] && Math.abs(b[0]) <= 90 && Math.abs(b[2]) <= 90 && Math.abs(b[1]) <= 180 && Math.abs(b[3]) <= 180;
      if (!ok || !e.id || BY[e.id] || ![GEB, TAL, INS, KUE, REG].includes(e.typ) || !e.name) continue;
      const x = {id: e.id, name: String(e.name), typ: e.typ, eltern: null, boxen: [b.slice()], poly: [], alias: [], county: [], nicht: [], in: null, prio: 0, anz: true, kreise: [], nkreise: [], nichtKreis: [], quelle: "eigen", tiefe: 99, land: e.land || ""};
      x.hull = b.slice();
      x.flaeche = (b[2] - b[0]) * (b[3] - b[1]) || 1e9;
      x.eigen = true;
      L.push(x);
      BY[x.id] = x;
    }
    cache.clear();
    PHR = null;
  };
  const api = {setEigene, regionMit, liste: L, nach: BY, von, namen, fuerSuche, bundesland, anzeige, regionTeile, regionText, phrasen, bericht, pruefen, fold, trifft: (id, la, ln, kr) => !!BY[id] && trifft(BY[id], la, ln, kr ? kreis(kr) : "")};
  if (typeof module !== "undefined") module.exports = api;
  return api;
})();
