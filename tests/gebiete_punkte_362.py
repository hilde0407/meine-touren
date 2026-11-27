"""Bekannte Punkte (Orte, Gipfel) je Gebiet für tests/test_gebiete_362.py: „<id> | Name lat,lng ; Name lat,lng“ – diese Punkte müssen im Gebiet liegen.
Zeilen mit „!“ davor: „!<id> | Name lat,lng ; …“ – diese Punkte dürfen NICHT im Gebiet liegen. Die Grenzen der Tabelle sind Näherungen; die Punkte sind bewusst Ortslagen, keine Randfälle."""

POS = """
lungau | Mauterndorf 47.14,13.67 ; Tamsweg 47.12,13.81
pongau | St. Johann im Pongau 47.35,13.20 ; Bad Gastein 47.11,13.13
pinzgau | Zell am See 47.32,12.80 ; Mittersill 47.28,12.48 ; Lofer 47.59,12.70
tennengau | Hallein 47.68,13.10 ; Golling 47.60,13.18
salzkammergut | Bad Ischl 47.71,13.62 ; St. Wolfgang 47.74,13.45 ; Gmunden 47.92,13.80
zillertal | Mayrhofen 47.16,11.86 ; Zell am Ziller 47.23,11.88
stubaital | Neustift 47.11,11.32 ; Fulpmes 47.16,11.35
oetztal | Sölden 46.97,11.01 ; Obergurgl 46.87,11.03
paznaun | Ischgl 47.01,10.29 ; Galtür 46.97,10.19
montafon | Schruns 47.08,9.91 ; Gaschurn 46.99,10.02
kaunertal | Feichten 46.96,10.70
kitzbueheler | Kitzbühel 47.45,12.39 ; Kirchberg 47.45,12.31
wilder-kaiser | Ellmau 47.52,12.30 ; Going 47.52,12.33
karwendel | Scharnitz 47.39,11.26 ; Hinterriß 47.49,11.57
dachstein | Dachstein-Hallstatt-Gosau 47.47,13.62 ; Ramsau 47.41,13.64 ; Gosau 47.55,13.53
hochkoenig | Maria Alm 47.40,12.90 ; Mühlbach 47.37,13.07
hohetauern | Heiligenblut 47.04,12.84 ; Rauris 47.22,13.00
glockner | Kals 47.00,12.64 ; Pasterze 47.08,12.73
venediger | Prägraten 47.00,12.37 ; Krimml 47.22,12.18
nockberge | Bad Kleinkirchheim 46.82,13.80 ; Turracher Höhe 46.92,14.00
gesaeuse | Admont 47.57,14.46 ; Johnsbach 47.57,14.62
hochschwab | Aflenz 47.55,15.23 ; Hochschwab 47.62,15.15
rax | Reichenau 47.69,15.85 ; Rax 47.69,15.70 ; Puchberg 47.79,16.00
bregenzerwald | Bezau 47.38,9.90 ; Schoppernau 47.31,10.02
kleinwalsertal | Riezlern 47.36,10.17
arlberg | St. Anton 47.13,10.27 ; Lech 47.21,10.14
ausserfern | Reutte 47.49,10.72 ; Elbigenalp 47.27,10.50
allgaeu | Oberstdorf 47.41,10.28 ; Kempten 47.73,10.31
berchtesgaden | Berchtesgaden 47.63,13.00 ; Königssee 47.58,12.98
wetterstein | Garmisch 47.49,11.10 ; Zugspitze 47.42,10.985
chiemgau | Ruhpolding 47.76,12.65 ; Reit im Winkl 47.68,12.47
tegernsee | Tegernsee 47.71,11.76 ; Schliersee 47.73,11.86
ammergau | Oberammergau 47.60,11.06 ; Füssen 47.57,10.70
wallis | Zermatt 46.02,7.75 ; Sion 46.23,7.36 ; Brig 46.32,7.99
bernoberland | Interlaken 46.69,7.86 ; Grindelwald 46.62,8.04 ; Kandersteg 46.50,7.67 ; Meiringen 46.73,8.19
jungfrau | Lauterbrunnen 46.59,7.91 ; Wengen 46.61,7.92
tessin | Lugano 46.00,8.95 ; Locarno 46.17,8.80 ; Bellinzona 46.19,9.02
graubuenden | Chur 46.85,9.53 ; Davos 46.80,9.84 ; St. Moritz 46.50,9.84 ; Disentis 46.70,8.85
engadin | St. Moritz 46.50,9.84 ; Scuol 46.80,10.30 ; Pontresina 46.49,9.90
zentralschweiz | Luzern 47.05,8.31 ; Engelberg 46.82,8.41 ; Altdorf 46.88,8.64
appenzell | Säntis 47.25,9.34 ; Appenzell 47.33,9.41
suedtirol | Bozen 46.50,11.35 ; Meran 46.67,11.16 ; Brixen 46.72,11.66 ; Bruneck 46.80,11.94 ; Sterzing 46.89,11.43 ; Toblach 46.73,12.22 ; St. Ulrich 46.57,11.67 ; Sulden 46.52,10.58 ; Schlanders 46.63,10.77 ; Kaltern 46.40,11.24 ; Sexten 46.70,12.36
schladminger | Schladming 47.39,13.69 ; Haus im Ennstal 47.37,13.53 ; Rohrmoos 47.36,13.70
radstaedter | Obertauern 47.25,13.56
maltatal | Malta 46.98,13.37
gailtaler | Greifenburg 46.75,13.18
sierra-nieves | Yunquera 36.74,-4.94 ; Tolox 36.69,-4.89
trentino | Trient 46.07,11.12 ; Rovereto 45.89,11.04 ; Riva 45.89,10.84 ; Madonna di Campiglio 46.23,10.83 ; Cles 46.36,11.03 ; Fiera di Primiero 46.17,11.82
dolomiten | Seiser Alm 46.54,11.62 ; Cortina 46.54,12.14 ; Drei Zinnen 46.62,12.30
brenta | Madonna di Campiglio 46.23,10.83 ; Molveno 46.14,10.96
ortler | Sulden 46.52,10.58 ; Trafoi 46.55,10.50
gardasee | Riva 45.89,10.84 ; Malcesine 45.76,10.81 ; Sirmione 45.49,10.61
aostatal | Aosta 45.74,7.32 ; Courmayeur 45.79,6.97 ; Cervinia 45.94,7.63 ; Gressoney 45.78,7.82
piemont | Turin 45.07,7.69 ; Cuneo 44.38,7.54 ; Alba 44.70,8.04 ; Biella 45.57,8.05
granparadiso | Cogne 45.61,7.35 ; Ceresole Reale 45.43,7.25
monviso | Crissolo 44.69,7.10 ; Monviso 44.667,7.092
monterosa | Alagna 45.85,7.93 ; Macugnaga 45.97,7.97 ; Monte Rosa 45.937,7.867
friaul | Udine 46.06,13.24 ; Pordenone 45.96,12.66 ; Tolmezzo 46.40,13.02 ; Cividale 46.09,13.43 ; Palmanova 45.90,13.31 ; Tarvis 46.50,13.58
karnische | Plöckenpass 46.61,12.95 ; Nassfeld 46.57,13.28 ; Sappada 46.57,12.70
julische | Bovec 46.34,13.55 ; Kranjska Gora 46.49,13.79 ; Bled 46.37,14.11 ; Triglav 46.378,13.837
kamniker | Jezersko 46.40,14.50 ; Krvavec 46.30,14.53 ; Logarska 46.40,14.63
savoyen | Chambéry 45.57,5.92 ; Annecy 45.90,6.13 ; Chamonix 45.92,6.87 ; Val d'Isère 45.45,6.98 ; Albertville 45.68,6.39
montblanc | Chamonix 45.92,6.87 ; Courmayeur 45.79,6.97 ; Mont Blanc 45.83,6.865 ; Champex 46.03,7.12
vercors | Villard-de-Lans 45.07,5.55 ; Vassieux 44.90,5.37 ; Grand Veymont 44.85,5.52
chartreuse | Saint-Pierre-de-Chartreuse 45.33,5.80 ; Grand Som 45.34,5.80
belledonne | Allevard 45.39,6.07 ; Croix de Belledonne 45.18,5.99
ecrins | La Bérarde 44.93,6.30 ; Les Deux Alpes 45.00,6.12 ; Pelvoux 44.89,6.49 ; Bourg-d'Oisans 45.05,6.03
mercantour | Saint-Martin-Vésubie 44.07,7.25 ; Barcelonnette 44.39,6.65 ; Isola 2000 44.18,7.15
vanoise | Pralognan 45.38,6.72 ; Tignes 45.47,6.91 ; Bourg-Saint-Maurice 45.62,6.77 ; Val Thorens 45.30,6.58
queyras | Saint-Véran 44.70,6.87 ; Abriès 44.79,6.93 ; Château-Queyras 44.77,6.75
harz | Wernigerode 51.84,10.79 ; Goslar 51.90,10.43 ; Thale 51.75,11.04 ; Quedlinburg 51.79,11.14
hochharz | Brocken 51.80,10.62 ; Schierke 51.76,10.66 ; Braunlage 51.72,10.61
suedharz | Nordhausen 51.50,10.79 ; Stolberg 51.57,11.00
saechsische-schweiz | Bastei 50.96,14.07 ; Bad Schandau 50.92,14.15 ; Königstein 50.92,14.06
boehmische-schweiz | Hřensko 50.87,14.23 ; Pravčická brána 50.87,14.31
erzgebirge | Oberwiesenthal 50.43,12.96 ; Altenberg 50.76,13.75 ; Seiffen 50.64,13.46 ; Annaberg 50.58,13.00 ; Klingenthal 50.36,12.47
thueringer-wald | Oberhof 50.70,10.73 ; Inselsberg 50.86,10.46 ; Suhl 50.61,10.69
rhoen | Wasserkuppe 50.50,9.94 ; Bischofsheim 50.40,10.00 ; Kreuzberg 50.37,9.98
schwarzwald | Feldberg 47.874,8.004 ; Freudenstadt 48.46,8.41 ; Triberg 48.13,8.23 ; Baiersbronn 48.50,8.38
schwarzwald-sued | Feldberg 47.874,8.004 ; Schluchsee 47.82,8.17
schwarzwald-mittel | Triberg 48.13,8.23 ; Wolfach 48.30,8.22
schwarzwald-nord | Freudenstadt 48.46,8.41 ; Baiersbronn 48.50,8.38
feldberg | Feldberg 47.874,8.004 ; Titisee 47.89,8.15 ; Schluchsee 47.82,8.17
schwaebische-alb | Hohenzollern 48.32,8.97 ; Bad Urach 48.49,9.40 ; Heidenheim 48.68,10.15 ; Blaubeuren 48.41,9.78
pfaelzerwald | Dahn 49.15,7.78 ; Neustadt 49.35,8.14 ; Annweiler 49.20,8.06 ; Kaiserslautern 49.44,7.77
eifel | Monschau 50.55,6.24 ; Gerolstein 50.22,6.66 ; Daun 50.20,6.83 ; Nürburg 50.34,6.95
hoheeifel | Nürburg 50.34,6.95 ; Adenau 50.38,6.93 ; Hohe Acht 50.39,7.00
hunsrueck | Idar-Oberstein 49.71,7.31 ; Erbeskopf 49.72,7.08 ; Simmern 49.98,7.52
taunus | Großer Feldberg 50.23,8.45 ; Bad Homburg 50.23,8.61 ; Königstein 50.18,8.47 ; Idstein 50.22,8.27
sauerland | Winterberg 51.19,8.53 ; Schmallenberg 51.15,8.28 ; Brilon 51.40,8.57 ; Olpe 51.03,7.85 ; Kahler Asten 51.18,8.49
teutoburger-wald | Hermannsdenkmal 51.91,8.84 ; Externsteine 51.87,8.92 ; Bielefeld 52.01,8.54 ; Bad Iburg 52.16,8.04
bayerischer-wald | Großer Arber 49.11,13.13 ; Zwiesel 49.02,13.24 ; Grafenau 48.86,13.40 ; Lusen 48.94,13.50
fichtelgebirge | Ochsenkopf 49.97,11.83 ; Wunsiedel 50.04,12.00 ; Fichtelberg 50.04,11.84
fraenkische-schweiz | Pottenstein 49.77,11.41 ; Muggendorf 49.80,11.27 ; Gößweinstein 49.77,11.33
odenwald | Michelstadt 49.68,9.00 ; Erbach 49.66,8.99 ; Lindenfels 49.72,8.77 ; Heidelberg 49.40,8.69
spessart | Aschaffenburg 49.97,9.15 ; Lohr 50.00,9.58 ; Bad Orb 50.23,9.35
westerwald | Montabaur 50.44,7.83 ; Westerburg 50.56,7.97 ; Hachenburg 50.66,7.82
siebengebirge | Drachenfels 50.66,7.21 ; Königswinter 50.67,7.20 ; Ölberg 50.69,7.28
weserbergland | Hameln 52.10,9.36 ; Höxter 51.77,9.38 ; Bad Pyrmont 51.99,9.25
solling | Neuhaus im Solling 51.75,9.57 ; Uslar 51.66,9.64
vogelsberg | Hoherodskopf 50.50,9.23 ; Schotten 50.50,9.10 ; Lauterbach 50.64,9.40
frankenwald | Kronach 50.24,11.33 ; Naila 50.33,11.70 ; Teuschnitz 50.40,11.39
oberpfaelzer-wald | Waldmünchen 49.38,12.70 ; Vohenstrauß 49.62,12.33 ; Furth im Wald 49.31,12.84
steigerwald | Ebrach 49.85,10.49 ; Scheinfeld 49.67,10.47
kellerwald | Edersee 51.18,9.05 ; Bad Wildungen 51.12,9.12
lueneburger-heide | Wilsede 53.15,9.93 ; Soltau 52.99,9.84 ; Bispingen 53.09,9.99
hegau | Singen 47.76,8.84 ; Hohentwiel 47.76,8.82 ; Engen 47.85,8.77
moseltal | Trier 49.76,6.64 ; Bernkastel-Kues 49.92,7.07 ; Cochem 50.15,7.17 ; Zell 50.03,7.19 ; Koblenz 50.36,7.59
vogesen | Grand Ballon 47.90,7.10 ; Hohneck 48.04,7.00 ; Gérardmer 48.07,6.88 ; Mont Sainte-Odile 48.44,7.40
jura | Chasseral 47.13,7.06 ; La Chaux-de-Fonds 47.10,6.83 ; Mont Tendre 46.58,6.30 ; Pontarlier 46.90,6.36 ; Saint-Claude 46.39,5.86
auvergne | Puy de Dôme 45.77,2.96 ; Sancy 45.53,2.81 ; Saint-Flour 45.03,3.09 ; Aurillac 44.93,2.44
cevennen | Florac 44.32,3.59 ; Mont Aigoual 44.12,3.58 ; Mont Lozère 44.45,3.73
ardennen | Houffalize 50.13,5.79 ; Bouillon 49.79,5.07 ; La Roche 50.18,5.58 ; Stavelot 50.39,5.93
hohesvenn | Botrange 50.50,6.09 ; Eupen 50.63,6.03 ; Malmedy 50.43,6.03
ostbelgien | Eupen 50.63,6.03 ; Sankt Vith 50.28,6.13 ; Büllingen 50.40,6.26
muellerthal | Echternach 49.81,6.42 ; Berdorf 49.82,6.35 ; Beaufort 49.84,6.30
riesengebirge | Schneekoppe 50.736,15.74 ; Špindlerův Mlýn 50.73,15.61 ; Harrachov 50.77,15.43 ; Karpacz 50.78,15.74
isergebirge | Jizerka 50.82,15.35 ; Bedřichov 50.82,15.00 ; Świeradów 50.91,15.34
adlergebirge | Deštné 50.30,16.35 ; Orlické Záhoří 50.25,16.40
altvater | Praděd 50.08,17.23 ; Jeseník 50.23,17.20
beskiden | Lysá hora 49.55,18.45 ; Szczyrk 49.72,19.03 ; Babia Góra 49.57,19.53 ; Krynica 49.42,20.96
boehmerwald | Lipno 48.63,14.22 ; Lusen 48.94,13.50 ; Kvilda 49.03,13.58
boehmisches-paradies | Hrubá Skála 50.52,15.22 ; Turnov 50.59,15.16 ; Prachov 50.50,15.28
boehmisches-mittelgebirge | Milešovka 50.55,13.93 ; Litoměřice 50.53,14.13 ; Ústí 50.66,14.04
hohetatra | Štrbské Pleso 49.12,20.06 ; Tatranská Lomnica 49.16,20.28 ; Gerlach 49.164,20.134 ; Rysy 49.18,20.09
westtatra | Roháče 49.20,19.75 ; Zuberec 49.27,19.62
zakopane | Zakopane 49.30,19.95 ; Kuźnice 49.27,19.98 ; Morskie Oko 49.20,20.07
niedere-tatra | Chopok 48.94,19.59 ; Jasná 49.03,19.59 ; Ďumbier 48.93,19.62
grosse-fatra | Blatnica 49.03,18.99 ; Krížna 48.98,19.06
kleine-fatra | Terchová 49.26,18.99 ; Vrátna 49.21,19.03
slowakisches-paradies | Hrabušice 48.94,20.35 ; Dedinky 48.86,20.33 ; Čingov 48.93,20.40
pieniny | Szczawnica 49.42,20.49 ; Červený Kláštor 49.39,20.40 ; Trzy Korony 49.41,20.42
kleine-karpaten | Pezinok 48.29,17.27 ; Smolenice 48.51,17.43 ; Záruby 48.45,17.37
eulengebirge | Sowia Góra 50.68,16.48 ; Walim 50.65,16.52
stolowe | Szczeliniec 50.49,16.34 ; Kudowa-Zdrój 50.44,16.24 ; Karłów 50.48,16.34
bieszczady | Wetlina 49.15,22.52 ; Tarnica 49.08,22.72 ; Ustrzyki Górne 49.09,22.62
swietokrzyskie | Kielce 50.87,20.63 ; Łysa Góra 50.86,21.05
masuren | Mikołajki 53.80,21.57 ; Giżycko 54.04,21.77 ; Mrągowo 53.86,21.30 ; Ełk 53.82,22.36
peakdistrict | Edale 53.37,-1.82 ; Bakewell 53.21,-1.67 ; Buxton 53.26,-1.91
lakedistrict | Keswick 54.60,-3.13 ; Ambleside 54.43,-2.96 ; Scafell Pike 54.454,-3.212 ; Windermere 54.38,-2.91
snowdonia | Snowdon 53.07,-4.08 ; Betws-y-Coed 53.09,-3.80 ; Dolgellau 52.74,-3.89
highlands | Fort William 56.82,-5.11 ; Ben Nevis 56.80,-5.00 ; Aviemore 57.19,-3.83 ; Inverness 57.48,-4.22
cairngorms | Aviemore 57.19,-3.83 ; Cairn Gorm 57.11,-3.64 ; Braemar 57.01,-3.40
glencoe | Glencoe 56.68,-5.10 ; Kinlochleven 56.71,-4.96
skye | Portree 57.41,-6.19 ; Dunvegan 57.44,-6.58 ; Broadford 57.24,-5.90 ; Sligachan 57.29,-6.16
wicklow | Glendalough 53.01,-6.33 ; Lugnaquilla 52.97,-6.46
kerry | Killarney 52.06,-9.50 ; Dingle 52.14,-10.27 ; Tralee 52.27,-9.70 ; Carrauntoohil 51.999,-9.74
dingle | Dingle 52.14,-10.27 ; Slea Head 52.10,-10.46
connemara | Clifden 53.49,-10.02 ; Kylemore 53.56,-9.88
pyrenaeen | Aneto 42.63,0.66 ; Gavarnie 42.73,-0.01 ; Canigó 42.52,2.46 ; Pic du Midi 42.94,0.14 ; Andorra la Vella 42.51,1.52 ; Roncesvalles 43.01,-1.32
pyr-aragon | Ordesa 42.65,-0.05 ; Benasque 42.60,0.52 ; Jaca 42.57,-0.55
pyr-katalan | Espot 42.58,1.09 ; Núria 42.40,2.15 ; Puigcerdà 42.43,1.93 ; Vielha 42.70,0.80
ordesa | Torla 42.63,-0.10 ; Pineta 42.65,0.10
aiguestortes | Espot 42.58,1.09 ; Boí 42.52,0.83
cadi | Gósol 42.23,1.70 ; Bagà 42.25,1.87
picos | Potes 43.15,-4.62 ; Covadonga 43.31,-5.06 ; Fuente Dé 43.15,-4.81 ; Poncebos 43.24,-4.83
sierra-nevada | Capileira 36.96,-3.35 ; Pico Veleta 37.06,-3.37 ; Mulhacén 37.05,-3.31
gredos | Plataforma de Gredos 40.26,-5.24 ; Candeleda 40.15,-5.25 ; Hoyos del Espino 40.34,-5.15
guadarrama | Navacerrada 40.79,-4.01 ; Peñalara 40.85,-3.95 ; Cercedilla 40.74,-4.05 ; Rascafría 40.91,-3.88
montserrat | Montserrat 41.59,1.84
montseny | Turó de l'Home 41.77,2.44 ; Viladrau 41.85,2.39
cazorla | Cazorla 37.91,-3.00 ; Coto Ríos 38.05,-2.89
caminito | El Chorro 36.92,-4.76 ; Gaitanes 36.93,-4.77
cabo-de-gata | Cabo de Gata 36.72,-2.19 ; San José 36.76,-2.11 ; Las Negras 36.87,-2.05
grazalema | Grazalema 36.76,-5.37 ; Zahara 36.84,-5.39
estrela | Seia 40.42,-7.70 ; Manteigas 40.40,-7.54 ; Torre 40.32,-7.61
geres | Gerês 41.73,-8.16 ; Soajo 41.87,-8.30
algarve | Faro 37.02,-7.93 ; Lagos 37.10,-8.67 ; Sagres 37.01,-8.94 ; Tavira 37.13,-7.65
rota-vicentina | Porto Covo 37.85,-8.78 ; Vila Nova de Milfontes 37.72,-8.78 ; Odeceixe 37.43,-8.80
la-gomera | Vallehermoso 28.18,-17.27 ; San Sebastián 28.09,-17.11 ; Valle Gran Rey 28.10,-17.34 ; Garajonay 28.12,-17.24
teneriffa | Teide 28.27,-16.64 ; Santa Cruz 28.47,-16.25 ; Los Gigantes 28.25,-16.84 ; Costa Adeje 28.08,-16.73
teide | Teide 28.27,-16.64 ; Vilaflor 28.16,-16.64
teno | Masca 28.30,-16.84
anaga | Taganana 28.55,-16.21
la-palma | Roque de los Muchachos 28.76,-17.89 ; Santa Cruz de la Palma 28.68,-17.76 ; Fuencaliente 28.48,-17.84
caldera | Roque de los Muchachos 28.76,-17.89 ; Caldera 28.72,-17.88
gran-canaria | Tejeda 27.99,-15.62 ; Maspalomas 27.76,-15.58 ; Las Palmas 28.12,-15.43
el-hierro | Valverde 27.81,-17.91
fuerteventura | Corralejo 28.74,-13.87 ; Betancuria 28.43,-14.06
lanzarote | Timanfaya 29.00,-13.75 ; Teguise 29.06,-13.56 ; Playa Blanca 28.86,-13.83
kanaren | Vallehermoso 28.18,-17.27 ; Teide 28.27,-16.64 ; Tejeda 27.99,-15.62 ; Timanfaya 29.00,-13.75
madeira | Funchal 32.65,-16.91 ; Pico Ruivo 32.76,-16.94 ; Porto Moniz 32.87,-17.17
porto-santo | Porto Santo 33.07,-16.34
sao-miguel | Ponta Delgada 37.74,-25.67 ; Sete Cidades 37.85,-25.79 ; Furnas 37.77,-25.32
pico | Pico 38.47,-28.40 ; Madalena 38.54,-28.53
faial | Horta 38.53,-28.63
sao-jorge | Velas 38.68,-28.21 ; Norte Grande 38.67,-28.05
terceira | Angra do Heroísmo 38.66,-27.22 ; Praia da Vitória 38.73,-27.06
graciosa | Santa Cruz da Graciosa 39.08,-28.00
flores | Santa Cruz das Flores 39.45,-31.13
corvo | Vila do Corvo 39.67,-31.11
santa-maria | Vila do Porto 36.95,-25.15
azoren | Pico 38.47,-28.40 ; Ponta Delgada 37.74,-25.67
mallorca | Palma 39.57,2.65 ; Formentor 39.96,3.21 ; Alcúdia 39.85,3.12 ; Cala Ratjada 39.71,3.46
tramuntana | Sóller 39.77,2.71 ; Valldemossa 39.71,2.62 ; Lluc 39.82,2.89 ; Puig Major 39.80,2.79
menorca | Maó 39.89,4.26 ; Ciutadella 40.00,3.84
ibiza | Ibiza 38.91,1.43 ; Sant Antoni 38.98,1.30
formentera | La Mola 38.66,1.58 ; Sant Francesc 38.70,1.43
reunion | Saint-Denis -20.88,55.45 ; Saint-Pierre -21.34,55.48
mafate | Marla -21.07,55.43 ; Grand Place -21.06,55.40 ; La Nouvelle -21.05,55.43
cilaos | Cilaos -21.135,55.47 ; Bras Rouge -21.15,55.46
salazie | Hell-Bourg -21.06,55.52 ; Salazie -21.03,55.54
piton-neiges | Piton des Neiges -21.099,55.479
piton-fournaise | Pas de Bellecombe -21.23,55.71 ; Dolomieu -21.244,55.708
maido | Maïdo -21.07,55.38 ; Maïdo Nord -21.05,55.35
plaine-cafres | Bourg-Murat -21.21,55.57
plaine-palmistes | Plaine-des-Palmistes -21.13,55.65
plaine-sables | Plaine des Sables -21.22,55.62
sud-sauvage | Saint-Joseph -21.38,55.62 ; Saint-Philippe -21.36,55.77
ostkueste | Saint-Benoît -21.03,55.71 ; Sainte-Rose -21.13,55.79
westkueste | Saint-Gilles -21.06,55.22 ; Saint-Leu -21.17,55.29 ; L'Étang-Salé -21.27,55.34
nordkueste | Saint-Denis -20.88,55.45 ; Sainte-Suzanne -20.91,55.61
korsika | Calenzana 42.50,8.86 ; Corte 42.31,9.15 ; Bonifacio 41.39,9.16 ; Bastia 42.70,9.45
sardinien | Cagliari 39.22,9.12 ; Alghero 40.56,8.32 ; Olbia 40.92,9.50
gennargentu | Fonni 40.12,9.25 ; Desulo 40.02,9.23 ; Punta La Marmora 40.00,9.32
supramonte | Oliena 40.28,9.40 ; Orgosolo 40.21,9.36 ; Cala Gonone 40.28,9.63
sizilien | Palermo 38.12,13.36 ; Catania 37.50,15.09 ; Syrakus 37.08,15.29 ; Ätna 37.75,15.00
aetna | Ätna 37.75,15.00 ; Nicolosi 37.62,15.02 ; Linguaglossa 37.84,15.14
madonie | Piano Battaglia 37.88,14.03 ; Castelbuono 37.93,14.09
nebrodi | Floresta 37.97,14.90 ; Lago Biviere 37.97,14.77 ; Randazzo 37.88,14.95
zingaro | Scopello 38.07,12.82 ; Zingaro 38.10,12.80 ; San Vito lo Capo 38.18,12.73
iblei | Ragusa 36.93,14.73 ; Noto 36.89,15.07 ; Pantalica 37.13,15.03
egadische | Favignana 37.93,12.33 ; Marettimo 37.97,12.06
aeolische | Lipari 38.47,14.95 ; Salina 38.55,14.85 ; Panarea 38.64,15.07
stromboli | Stromboli 38.79,15.21
vulcano | Vulcano 38.404,14.962
lipari | Lipari 38.47,14.95
elba | Portoferraio 42.81,10.33 ; Monte Capanne 42.78,10.17
kreta | Chania 35.51,24.02 ; Heraklion 35.34,25.13 ; Samaria 35.27,23.97 ; Zakros 35.10,26.26
zypern | Troodos 34.94,32.87 ; Paphos 34.78,32.42 ; Larnaka 34.92,33.63
malta | Valletta 35.90,14.51 ; Victoria Gozo 36.04,14.24
rhodos | Lindos 36.09,28.09 ; Rhodos 36.44,28.22
santorin | Fira 36.42,25.43 ; Oia 36.46,25.38
island | Reykjavik 64.15,-21.94 ; Akureyri 65.68,-18.10
laugavegur | Landmannalaugar 63.99,-19.06 ; Hrafntinnusker 63.93,-19.20 ; Álftavatn 63.85,-19.15 ; Emstrur 63.77,-19.35
thorsmoerk | Húsadalur 63.68,-19.52 ; Básar 63.68,-19.49
lofoten | Svolvær 68.23,14.57 ; Reine 67.93,13.09 ; Henningsvær 68.15,14.20
kapverden | Praia 14.93,-23.51 ; Mindelo 16.89,-25.00 ; Sal 16.74,-22.93
santo-antao | Ribeira Grande 17.18,-25.07 ; Paul 17.14,-25.07
mauritius | Le Morne -20.45,57.31 ; Port Louis -20.16,57.50 ; Black River Gorges -20.40,57.43
toskana | Florenz 43.77,11.25 ; Siena 43.32,11.33 ; Pisa 43.72,10.40 ; Lucca 43.84,10.50 ; Arezzo 43.46,11.88
chianti | Greve in Chianti 43.59,11.31 ; Radda 43.49,11.37 ; Gaiole 43.44,11.43
val-d-orcia | Pienza 43.08,11.68 ; Montalcino 43.06,11.49 ; San Quirico 43.06,11.60 ; Radicofani 42.90,11.77
apuaner | Pania della Croce 44.03,10.27 ; Carrara 44.08,10.10 ; Castelnuovo 44.11,10.41
cinque-terre | Vernazza 44.135,9.68 ; Monterosso 44.145,9.65 ; Riomaggiore 44.10,9.74
ligurien | Genua 44.41,8.93 ; Sanremo 43.82,7.78 ; La Spezia 44.10,9.82 ; Savona 44.31,8.48
umbrien | Perugia 43.11,12.39 ; Assisi 43.07,12.62 ; Spoleto 42.74,12.74 ; Orvieto 42.72,12.11 ; Terni 42.56,12.64
marken | Pesaro 43.91,12.91 ; Ancona 43.62,13.52 ; Urbino 43.73,12.64 ; Ascoli Piceno 42.85,13.58 ; Macerata 43.30,13.45
sibillini | Monte Vettore 42.82,13.27 ; Montemonaco 42.89,13.32 ; Amandola 42.98,13.35
abruzzen | L'Aquila 42.35,13.40 ; Pescara 42.46,14.21 ; Chieti 42.35,14.17 ; Teramo 42.66,13.70 ; Sulmona 42.05,13.93 ; Pescasseroli 41.81,13.79
gransasso | Campo Imperatore 42.44,13.55 ; Corno Grande 42.47,13.57 ; Assergi 42.42,13.52
majella | Caramanico 42.15,14.00 ; Blockhaus 42.14,14.10 ; Monte Amaro 42.08,14.09 ; Sulmona 42.05,13.93
latium | Rom 41.90,12.50 ; Viterbo 42.42,12.11 ; Latina 41.47,12.90 ; Rieti 42.40,12.86 ; Gaeta 41.21,13.57
kampanien | Neapel 40.85,14.27 ; Salerno 40.68,14.77 ; Caserta 41.07,14.33 ; Benevento 41.13,14.78 ; Capri 40.55,14.24
amalfi | Amalfi 40.63,14.60 ; Positano 40.63,14.48 ; Ravello 40.65,14.61 ; Sorrent 40.63,14.38
cilento | Paestum 40.42,15.00 ; Agropoli 40.35,14.99 ; Vallo della Lucania 40.23,15.26 ; Sapri 40.07,15.63
vesuv | Vesuv 40.82,14.43 ; Ercolano 40.81,14.35
apulien | Bari 41.12,16.87 ; Foggia 41.46,15.55 ; Lecce 40.35,18.17 ; Martina Franca 40.70,17.34 ; Brindisi 40.63,17.94
gargano | Vieste 41.88,16.18 ; Monte Sant'Angelo 41.71,15.96 ; Peschici 41.95,16.02
salento | Lecce 40.35,18.17 ; Otranto 40.15,18.49 ; Gallipoli 40.06,17.98 ; Santa Maria di Leuca 39.80,18.36
basilikata | Potenza 40.64,15.80 ; Matera 40.67,16.60 ; Maratea 39.99,15.71
kalabrien | Cosenza 39.30,16.25 ; Catanzaro 38.91,16.59 ; Tropea 38.68,15.90 ; Crotone 39.08,17.13 ; Gambarie 38.16,15.84
pollino | Rotonda 39.94,16.05 ; Civita 39.84,16.35 ; Serra Dolcedorme 39.95,16.30
aspromonte | Gambarie 38.16,15.84 ; Montalto 38.17,15.92
sila | Camigliatello Silano 39.34,16.43 ; Lorica 39.25,16.55
ruegen | Sassnitz 54.51,13.64 ; Binz 54.40,13.60 ; Putbus 54.35,13.48 ; Kap Arkona 54.68,13.43 ; Gingst 54.50,13.28
jasmund | Königsstuhl 54.568,13.60 ; Sassnitz 54.51,13.64
moenchgut | Göhren 54.34,13.74 ; Thiessow 54.27,13.72
hiddensee | Kloster 54.59,13.11 ; Vitte 54.56,13.12 ; Neuendorf 54.52,13.10
usedom | Heringsdorf 53.95,14.17 ; Zinnowitz 54.09,13.91 ; Peenemünde 54.16,13.77 ; Ahlbeck 53.94,14.19
darss | Ahrenshoop 54.38,12.42 ; Prerow 54.45,12.58 ; Zingst 54.43,12.69 ; Wustrow 54.35,12.40
nordfriesische | Westerland 54.91,8.31 ; Wyk auf Föhr 54.69,8.57 ; Wittdün 54.63,8.38 ; Pellworm 54.50,8.65
sylt | Westerland 54.91,8.31 ; List 55.02,8.43 ; Hörnum 54.76,8.29
amrum | Wittdün 54.63,8.38 ; Nebel 54.64,8.34
foehr | Wyk auf Föhr 54.69,8.57
ostfriesische | Borkum 53.58,6.67 ; Juist 53.68,7.00 ; Norderney 53.71,7.15 ; Langeoog 53.75,7.50 ; Spiekeroog 53.77,7.70 ; Wangerooge 53.79,7.90
helgoland | Helgoland 54.18,7.89
normandie | Mont-Saint-Michel 48.64,-1.51 ; Étretat 49.71,0.20 ; Caen 49.18,-0.37 ; Cherbourg 49.64,-1.62 ; Rouen 49.44,1.10 ; Dieppe 49.92,1.08
bretagne | Brest 48.39,-4.49 ; Quimper 48.00,-4.10 ; Saint-Malo 48.65,-2.03 ; Rennes 48.11,-1.68
calanques | Cassis 43.21,5.54 ; Sormiou 43.21,5.42 ; En-Vau 43.21,5.50 ; Luminy 43.23,5.44
cornwall | Land's End 50.07,-5.71 ; Newquay 50.41,-5.07 ; Padstow 50.54,-4.94 ; Tintagel 50.66,-4.76 ; St Ives 50.21,-5.48
pembrokeshire | St Davids 51.88,-5.27 ; Tenby 51.67,-4.70 ; Fishguard 52.00,-4.99
dalmatien | Split 43.51,16.44 ; Dubrovnik 42.65,18.09 ; Zadar 44.12,15.23 ; Makarska 43.30,17.02 ; Šibenik 43.73,15.89
istrien | Pula 44.87,13.85 ; Rovinj 45.08,13.64 ; Poreč 45.23,13.59 ; Pazin 45.24,13.93
kvarner | Rijeka 45.33,14.44 ; Krk 45.03,14.57 ; Cres 44.96,14.41 ; Lošinj 44.53,14.47 ; Rab 44.76,14.76
lykien | Fethiye 36.65,29.12 ; Kaş 36.20,29.64 ; Olympos 36.40,30.47 ; Kalkan 36.26,29.41
jotunheimen | Besseggen 61.51,8.70 ; Galdhøpiggen 61.64,8.31 ; Gjendesheim 61.49,8.77
hardangervidda | Finse 60.60,7.50 ; Haukeliseter 59.81,7.18 ; Eidfjord 60.47,7.07 ; Vøringsfossen 60.43,7.25
lyngen | Lyngseidet 69.58,20.21 ; Skibotn 69.38,20.27
rondane | Rondvassbu 61.92,9.80 ; Rondslottet 61.89,9.78 ; Mysuseter 61.85,10.09
lappland | Rovaniemi 66.50,25.72 ; Kiruna 67.86,20.23 ; Levi 67.80,24.80 ; Saariselkä 68.41,27.41 ; Kilpisjärvi 69.05,20.80
kebnekaise | Kebnekaise 67.90,18.57 ; Nikkaluokta 67.85,19.00
sarek | Sarek 67.30,17.60 ; Rapadalen 67.28,17.65
abisko | Abisko 68.35,18.82 ; Abiskojaure 68.31,18.50
rumaenische-karpaten | Moldoveanu 45.60,24.74 ; Sinaia 45.35,25.55 ; Retezat 45.37,22.90 ; Piatra Craiului 45.53,25.22 ; Pietrosul Rodnei 47.53,24.64 ; Ceahlău 46.97,25.95
rila | Rila-Kloster 42.13,23.34 ; Musala 42.18,23.58 ; Borovets 42.27,23.60
pirin | Bansko 41.84,23.49 ; Vihren 41.77,23.40 ; Melnik 41.52,23.40
durmitor | Žabljak 43.15,19.12 ; Bobotov Kuk 43.13,19.03 ; Crno Jezero 43.15,19.09
prokletije | Theth 42.40,19.77 ; Valbona 42.45,19.88 ; Plav 42.60,19.95
hoher-atlas | Toubkal 31.06,-7.92 ; Imlil 31.14,-7.92
annapurna | Manang 28.67,84.02 ; Thorong La 28.80,83.94 ; Annapurna Base Camp 28.53,83.88
everest | Lukla 27.69,86.73 ; Namche Bazaar 27.80,86.71 ; Everest 27.99,86.93
kilimandscharo | Uhuru Peak -3.07,37.35 ; Marangu -3.25,37.52 ; Machame -3.20,37.25
hawaii-big | Hilo 19.72,-155.08 ; Mauna Kea 19.82,-155.47 ; Kona 19.64,-155.99
maui | Haleakalā 20.71,-156.25 ; Lahaina 20.87,-156.68
oahu | Honolulu 21.31,-157.86 ; Diamond Head 21.26,-157.81
kauai | Nā Pali 22.17,-159.65 ; Waimea 22.02,-159.67
torres-del-paine | Torres del Paine -51.00,-73.00
fitz-roy | El Chaltén -49.33,-72.89 ; Fitz Roy -49.27,-73.04
neuseeland-nord | Auckland -36.85,174.76 ; Wellington -41.29,174.78 ; Tongariro -39.13,175.63 ; Rotorua -38.14,176.25
neuseeland-sued | Queenstown -45.03,168.66 ; Mount Cook -43.59,170.14 ; Milford Sound -44.67,167.93 ; Abel Tasman -40.90,172.90 ; Christchurch -43.53,172.64
osttirol | Lienz 46.83,12.77 ; Matrei in Osttirol 47.00,12.53 ; Sillian 46.7467,12.4167 ; Obertilliach 46.69,12.60 ; Kals 47.00,12.64
villgratental | Innervillgraten 46.80,12.32 ; Außervillgraten 46.77,12.38
defereggen | St. Jakob in Defereggen 46.91,12.35 ; St. Veit in Defereggen 46.92,12.45
virgental | Virgen 47.00,12.45 ; Prägraten 47.00,12.37
lienzer-dolomiten | Karlsbader Hütte 46.76,12.80 ; Dolomitenhütte 46.77,12.79
innsbruck | Patsch 47.21,11.45 ; Igls 47.23,11.42 ; Innsbruck 47.26,11.39 ; Aldrans 47.25,11.46
tuxer | Patscherkofel 47.21,11.46 ; Glungezer 47.22,11.67 ; Tulfes 47.28,11.54
raetikon | Lünersee 47.05,9.77 ; Bürserberg 47.13,9.74 ; Gargellen 46.97,9.86
brandnertal | Brand 47.07,9.72 ; Bürserberg 47.13,9.74 ; Bludenz 47.155,9.82
oetscher | Ötscher 47.86,15.21 ; Lunz am See 47.90,15.05 ; Lackenhof 47.85,15.17
wachau | Dürnstein 48.39,15.52 ; Spitz an der Donau 48.38,15.42 ; Melk 48.23,15.33
neusiedlersee | Podersdorf 47.86,16.83 ; Illmitz 47.77,16.84 ; Rust 47.80,16.67
villach | Villach 46.61,13.85 ; Ossiach 46.67,13.98 ; Gerlitzen 46.69,13.92
peloponnes | Patras 38.25,21.73 ; Kalamata 37.04,22.11 ; Nafplio 37.57,22.80 ; Korinth 37.94,22.93 ; Monemvasia 36.69,23.04 ; Olympia 37.64,21.63 ; Sparta 37.07,22.43
messenien | Kalamata 37.04,22.11 ; Pylos 36.91,21.70 ; Mavromati 37.18,21.92
mani | Areopoli 36.67,22.38 ; Vathia 36.47,22.48 ; Kardamyli 36.89,22.23
taygetos | Taygetos Gipfel 36.96,22.35 ; Mystras 37.07,22.37
parnon | Kosmas 37.12,22.63 ; Kastanitsa 37.10,22.60
arkadien | Tripoli 37.51,22.37 ; Dimitsana 37.60,22.03 ; Megalopoli 37.40,22.14
argolis | Nafplio 37.57,22.80 ; Epidavros 37.63,23.08 ; Mykene 37.73,22.76
ilia | Olympia 37.64,21.63 ; Pyrgos 37.67,21.44 ; Zacharo 37.48,21.65
# 3.70.0 Abgleich mit dem Rother-Wanderführer-Katalog
cote-d-azur | Nizza 43.70,7.27 ; Cannes 43.55,7.01 ; Menton 43.78,7.50 ; Saint-Tropez 43.27,6.64 ; Grasse 43.66,6.92
burgund | Dijon 47.32,5.04 ; Beaune 47.02,4.84 ; Auxerre 47.80,3.57 ; Vézelay 47.47,3.75 ; Cluny 46.43,4.66
dordogne | Sarlat 44.89,1.22 ; Périgueux 45.18,0.72 ; Bergerac 44.85,0.48 ; Cahors 44.45,1.44 ; Rocamadour 44.80,1.62
dauphine | Grenoble 45.19,5.72 ; Valence 44.93,4.89 ; Gap 44.56,6.08 ; Briançon 44.90,6.64 ; Die 44.75,5.37
muensterland | Münster 51.96,7.63 ; Coesfeld 51.94,7.17 ; Rheine 52.28,7.44
oberlausitz | Bautzen 51.18,14.43 ; Görlitz 51.15,14.99 ; Zittau 50.90,14.81
seenplatte | Waren 53.52,12.68 ; Neustrelitz 53.36,13.06 ; Röbel 53.38,12.61
bergisches-land | Wuppertal 51.26,7.15 ; Solingen 51.17,7.08 ; Wipperfürth 51.12,7.40
siegerland | Siegen 50.87,8.02 ; Bad Berleburg 51.05,8.39
isarwinkel | Bad Tölz 47.76,11.56 ; Lenggries 47.68,11.57 ; Walchensee 47.60,11.35
pfaffenwinkel | Weilheim 47.84,11.14 ; Peiting 47.80,10.93 ; Murnau 47.68,11.20
kaiserstuhl | Breisach 48.03,7.58 ; Endingen 48.14,7.70
elbtalaue | Hitzacker 53.15,10.99 ; Dömitz 53.14,11.25
uckermark | Prenzlau 53.32,13.86 ; Angermünde 53.02,14.00 ; Templin 53.12,13.50
emsland | Meppen 52.69,7.29 ; Lingen 52.52,7.32 ; Papenburg 53.08,7.40 ; Nordhorn 52.43,7.07
ostfriesland | Leer 53.23,7.45 ; Aurich 53.47,7.48 ; Norden 53.60,7.20 ; Emden 53.37,7.21
rheinhessen | Alzey 49.75,8.12 ; Ingelheim 49.97,8.06 ; Bingen 49.97,7.90
kraichgau | Sinsheim 49.25,8.88 ; Bruchsal 49.12,8.60 ; Eppingen 49.14,8.92
taubertal | Rothenburg ob der Tauber 49.38,10.18 ; Wertheim 49.76,9.52 ; Bad Mergentheim 49.49,9.77
altmuehltal | Eichstätt 48.89,11.18 ; Kelheim 48.92,11.87 ; Beilngries 49.03,11.47
saale-unstrut | Naumburg 51.15,11.81 ; Freyburg 51.21,11.77
baederdreieck | Bad Füssing 48.35,13.30 ; Bad Griesbach 48.43,13.20 ; Bad Birnbach 48.43,12.97
bodensee | Konstanz 47.66,9.17 ; Friedrichshafen 47.65,9.48 ; Lindau 47.55,9.68 ; Überlingen 47.77,9.17
wienerwald | Baden 48.01,16.23 ; Mödling 48.09,16.29 ; Klosterneuburg 48.30,16.32 ; Purkersdorf 48.21,16.18
pitztal | Imst 47.24,10.74 ; Pitztaler Gletscher 46.93,10.87 ; Jerzens 47.13,10.77
lesachtal | Kötschach 46.66,13.00 ; Maria Luggau 46.67,12.80 ; Liesing 46.67,12.88
seefeld | Seefeld 47.33,11.19 ; Leutasch 47.35,11.15
gastein | Bad Gastein 47.11,13.13 ; Bad Hofgastein 47.17,13.10 ; Dorfgastein 47.20,13.08
mariazell | Mariazell 47.77,15.32 ; Erlaufsee 47.78,15.28
moelltal | Winklern 46.86,12.95 ; Obervellach 46.93,13.20 ; Flattach 46.90,13.15
woerthersee | Velden 46.62,14.04 ; Pörtschach 46.63,14.17 ; Klagenfurt 46.62,14.31
millstaettersee | Millstatt 46.80,13.58 ; Seeboden 46.82,13.51
grazer-hausberge | Graz 47.07,15.44 ; Schöckl 47.20,15.47 ; Gratkorn 47.13,15.34
oststeiermark | Hartberg 47.28,15.97 ; Fürstenfeld 47.05,16.08 ; Weiz 47.22,15.62 ; Feldbach 46.95,15.89
leithagebirge | Eisenstadt 47.85,16.52 ; Mattersburg 47.74,16.40 ; Forchtenstein 47.69,16.32
kalkalpen | Windischgarsten 47.72,14.35 ; Molln 47.86,14.24 ; Reichraming 47.87,14.46
glarnerland | Glarus 47.04,9.07 ; Elm 46.92,9.17 ; Linthal 46.92,9.00
zuerichsee | Zürich 47.37,8.54 ; Rapperswil 47.23,8.82 ; Zug 47.17,8.52 ; Einsiedeln 47.13,8.75
genfersee | Lausanne 46.52,6.63 ; Montreux 46.43,6.91 ; Genf 46.20,6.15 ; Évian 46.40,6.59 ; Vevey 46.46,6.84
vierwaldstaettersee | Luzern 47.05,8.31 ; Brunnen 47.00,8.60 ; Flüelen 46.90,8.62 ; Weggis 47.03,8.43
emmental | Langnau 46.94,7.79 ; Burgdorf 47.06,7.63 ; Entlebuch 46.99,8.06 ; Huttwil 47.11,7.85
gruyere | Gruyères 46.58,7.08 ; Charmey 46.62,7.16 ; Les Diablerets 46.35,7.16 ; Château-d'Oex 46.48,7.14
surselva | Disentis 46.70,8.85 ; Ilanz 46.77,9.20 ; Flims 46.83,9.28 ; Vals 46.62,9.18
davos | Davos 46.80,9.84 ; Klosters 46.87,9.88 ; Küblis 46.91,9.78
vinschgau | Schlanders 46.63,10.77 ; Mals 46.69,10.55 ; Latsch 46.62,10.87
meran | Meran 46.67,11.16 ; Schenna 46.69,11.19 ; Algund 46.68,11.12 ; Lana 46.61,11.16
bozen | Bozen 46.50,11.35 ; Kaltern 46.40,11.24 ; Eppan 46.47,11.27 ; Klobenstein 46.55,11.46
sterzing | Sterzing 46.89,11.43 ; Gossensaß 46.97,11.47 ; Franzensfeste 46.79,11.62
ahrntal | Sand in Taufers 46.90,11.95 ; Steinhaus 47.01,12.06 ; Luttach 46.94,11.98
antholz | Antholz 46.86,12.15 ; St. Magdalena Gsies 46.79,12.20 ; Rasen 46.80,12.10
pustertal | Bruneck 46.80,11.94 ; Toblach 46.73,12.22 ; Innichen 46.735,12.28 ; Olang 46.76,12.03
seiser-alm | Seis 46.54,11.56 ; Kastelruth 46.57,11.57 ; Compatsch 46.54,11.63 ; Völs 46.52,11.54
groeden | St. Ulrich 46.58,11.67 ; Selva 46.55,11.76 ; St. Christina 46.56,11.72
fassatal | Canazei 46.48,11.77 ; Moena 46.37,11.66 ; Vigo di Fassa 46.43,11.69
gadertal | Corvara 46.55,11.87 ; La Villa 46.58,11.89 ; St. Vigil 46.70,12.01 ; Pedraces 46.58,11.93
sextner | Sexten 46.70,12.35 ; Toblach 46.73,12.22 ; Misurina 46.58,12.25 ; Drei Zinnen 46.62,12.30
cortina | Cortina 46.54,12.14 ; Falzaregopass 46.52,12.01 ; Cinque Torri 46.50,12.04 ; Passo Giau 46.48,12.04
eggental | Welschnofen 46.43,11.53 ; Karersee 46.41,11.58 ; Latemar 46.37,11.57 ; Obereggen 46.37,11.52
lago-maggiore | Stresa 45.89,8.53 ; Locarno 46.17,8.80 ; Arona 45.76,8.56 ; Luino 46.00,8.75 ; Orta San Giulio 45.80,8.41
comer-see | Como 45.81,9.08 ; Lecco 45.86,9.40 ; Menaggio 46.02,9.23 ; Bellagio 45.99,9.26 ; Colico 46.14,9.38
adamello | Ponte di Legno 46.26,10.51 ; Pinzolo 46.16,10.76 ; Edolo 46.18,10.33 ; Passo del Tonale 46.26,10.58
vizentiner | Asiago 45.88,11.51 ; Recoaro 45.70,11.22 ; Pian delle Fugazze 45.78,11.22 ; Folgaria 45.91,11.17
golf-neapel | Pozzuoli 40.82,14.12 ; Anacapri 40.56,14.22 ; Ischia 40.73,13.90 ; Sorrent 40.63,14.37 ; Neapel 40.85,14.27
galicien | Santiago de Compostela 42.88,-8.54 ; Vigo 42.24,-8.72 ; A Coruña 43.37,-8.40 ; Lugo 43.01,-7.56 ; Ourense 42.34,-7.86 ; Fisterra 42.91,-9.26
kantabrien | Santander 43.46,-3.81 ; Potes 43.15,-4.62 ; Fuente Dé 43.15,-4.81 ; Santillana del Mar 43.39,-4.11 ; Reinosa 43.00,-4.14 ; Laredo 43.41,-3.41
asturien | Oviedo 43.36,-5.85 ; Gijón 43.54,-5.66 ; Covadonga 43.31,-5.06 ; Llanes 43.42,-4.75 ; Cangas de Onís 43.35,-5.14
baskenland | Bilbao 43.26,-2.93 ; San Sebastián 43.32,-1.98 ; Vitoria 42.85,-2.67 ; Bayonne 43.49,-1.47 ; Saint-Jean-Pied-de-Port 43.16,-1.24
costa-brava | Roses 42.26,3.18 ; Cadaqués 42.29,3.28 ; Palafrugell 41.92,3.16 ; Tossa de Mar 41.72,2.93 ; Portbou 42.43,3.16
costa-daurada | Tarragona 41.12,1.25 ; Salou 41.08,1.14 ; Cambrils 41.07,1.06 ; Siurana 41.26,0.93 ; Sitges 41.24,1.81 ; Deltebre 40.72,0.72
costa-blanca | Alicante 38.35,-0.48 ; Benidorm 38.54,-0.13 ; Calpe 38.64,0.04 ; Dénia 38.84,0.11 ; Alcoy 38.70,-0.47 ; Torrevieja 37.98,-0.68
alentejo | Évora 38.57,-7.91 ; Beja 38.02,-7.86 ; Sines 37.96,-8.87 ; Portalegre 39.29,-7.43 ; Mértola 37.64,-7.66
nordportugal | Porto 41.15,-8.61 ; Braga 41.55,-8.43 ; Vila Real 41.30,-7.74 ; Bragança 41.81,-6.76 ; Guimarães 41.44,-8.30 ; Viana do Castelo 41.69,-8.83
korfu | Kerkyra 39.62,19.92 ; Paleokastritsa 39.67,19.70 ; Kassiopi 39.79,19.91 ; Pantokrator 39.75,19.87
chalkidiki | Polygyros 40.38,23.44 ; Nikiti 40.21,23.68 ; Ouranoupoli 40.32,23.98 ; Kallithea 39.98,23.41
thassos | Limenas 40.78,24.71 ; Potos 40.67,24.69
olymp | Litochoro 40.10,22.50 ; Mytikas 40.085,22.358 ; Prionia 40.10,22.40
pilion | Volos 39.36,22.94 ; Zagora 39.43,23.10 ; Tsagarada 39.37,23.20 ; Milies 39.33,23.15
kefalonia | Argostoli 38.18,20.49 ; Fiskardo 38.46,20.58 ; Sami 38.25,20.65 ; Lixouri 38.20,20.43
ithaka | Vathy 38.37,20.72 ; Kioni 38.45,20.69 ; Stavros 38.43,20.67
zakynthos | Zakynthos 37.78,20.90 ; Keri 37.66,20.83 ; Navagio 37.86,20.62
samos | Pythagoreio 37.69,26.94 ; Karlovasi 37.79,26.70 ; Kokkari 37.79,26.89
ikaria | Agios Kirykos 37.61,26.30 ; Evdilos 37.63,26.17 ; Armenistis 37.63,26.10
patmos | Skala 37.31,26.55 ; Chora 37.31,26.54
fourni | Fourni 37.60,26.51
dovrefjell | Hjerkinn 62.22,9.55 ; Kongsvoll 62.30,9.60 ; Snøhetta 62.32,9.27
vesteraalen | Sortland 68.70,15.42 ; Andenes 69.32,16.12
gotland | Visby 57.64,18.30 ; Fårösund 57.86,19.06 ; Hoburgen 56.92,18.15 ; Slite 57.71,18.80
oeland | Borgholm 56.88,16.65 ; Färjestaden 56.65,16.45 ; Byxelkrok 57.33,17.00
bornholm | Rønne 55.10,14.70 ; Svaneke 55.13,15.14 ; Gudhjem 55.20,14.97 ; Dueodde 55.00,15.07
faeroeer | Tórshavn 62.01,-6.77 ; Mykines 62.10,-7.65 ; Gásadalur 62.11,-7.44 ; Saksun 62.25,-7.18 ; Tvøroyri 61.55,-6.80
kanalinseln | St. Helier 49.19,-2.11 ; St. Peter Port 49.46,-2.54 ; Sark 49.43,-2.36 ; Alderney 49.72,-2.20
devon | Exeter 50.72,-3.53 ; Plymouth 50.37,-4.14 ; Princetown 50.54,-4.00 ; Ilfracombe 51.21,-4.12 ; Salcombe 50.24,-3.77 ; Torquay 50.46,-3.53
molokai | Kaunakakai 21.09,-157.02 ; Kalaupapa 21.19,-156.98
tasmanien | Hobart -42.88,147.33 ; Cradle Mountain -41.65,145.95 ; Launceston -41.44,147.14 ; Freycinet -42.15,148.30
"""

NEG = """
!suedtirol | Trient 46.07,11.12 ; Cortina 46.54,12.14 ; Madonna di Campiglio 46.23,10.83 ; Moena 46.38,11.66 ; Innsbruck 47.26,11.39 ; Verona 45.44,10.99
!trentino | Bozen 46.50,11.35 ; Meran 46.67,11.16 ; Verona 45.44,10.99 ; Belluno 46.14,12.22
!schladminger | Ramsau am Dachstein 47.42,13.64 ; Radstadt 47.38,13.46 ; Liezen 47.57,14.24
!maltatal | Spittal an der Drau 46.80,13.49 ; Gmünd in Kärnten 46.91,13.53
!gailtaler | Kötschach-Mauthen 46.66,13.00
!sierra-nieves | Ronda 36.74,-5.17 ; Málaga 36.72,-4.42
!suedtirol | Sillian 46.746,12.417 ; Innervillgraten 46.78,12.37 ; Kartitsch 46.74,12.50 ; Rabbi 46.40,10.85
!lungau | Radstadt 47.38,13.46 ; Schladming 47.39,13.69 ; Salzburg 47.80,13.04
!pinzgau | Kitzbühel 47.45,12.39 ; Salzburg 47.80,13.04
!wallis | Chamonix 45.92,6.87 ; Interlaken 46.69,7.86 ; Domodossola 46.11,8.29 ; Bern 46.95,7.45
!tessin | Como 45.81,9.08 ; Chur 46.85,9.53
!graubuenden | Lugano 46.00,8.95 ; Livigno 46.54,10.14 ; Tirano 46.21,10.17
!aostatal | Chamonix 45.92,6.87 ; Zermatt 46.02,7.75 ; Turin 45.07,7.69
!piemont | Genua 44.41,8.93 ; Mailand 45.46,9.19 ; Aosta 45.74,7.32
!savoyen | Genf 46.20,6.14 ; Grenoble 45.19,5.72 ; Lausanne 46.52,6.63
!jura | Genf 46.20,6.14 ; Lausanne 46.52,6.63 ; Bern 46.95,7.45
!toskana | Bologna 44.49,11.34 ; Perugia 43.11,12.39 ; Rom 41.90,12.50
!umbrien | Rieti 42.40,12.86 ; Florenz 43.77,11.25
!apulien | Matera 40.67,16.60 ; Neapel 40.85,14.27
!ligurien | Turin 45.07,7.69 ; Mailand 45.46,9.19
!normandie | Paris 48.86,2.35 ; Chartres 48.45,1.49 ; Rennes 48.11,-1.68
!bretagne | Nantes 47.22,-1.55 ; Mont-Saint-Michel 48.64,-1.51
!schwarzwald | Stuttgart 48.78,9.18 ; Basel 47.56,7.59 ; Straßburg 48.58,7.75 ; Karlsruhe 49.01,8.40
!taunus | Frankfurt 50.11,8.68 ; Wiesbaden 50.08,8.24
!erzgebirge | Dresden 51.05,13.74 ; Chemnitz 50.83,12.92
!thueringer-wald | Erfurt 50.98,11.03
!rhoen | Würzburg 49.79,9.93
!pyrenaeen | Madrid 40.42,-3.70 ; Barcelona 41.39,2.17 ; Toulouse 43.60,1.44 ; Pau 43.30,-0.37 ; Pamplona 42.82,-1.64
!highlands | Edinburgh 55.95,-3.19 ; Glasgow 55.86,-4.25
!peakdistrict | Manchester 53.48,-2.24 ; Sheffield 53.38,-1.47
!kerry | Galway 53.27,-9.05 ; Dublin 53.35,-6.26
!wicklow | Dublin 53.35,-6.26
!cornwall | Plymouth 50.37,-4.14 ; Exeter 50.72,-3.53
!istrien | Triest 45.65,13.77
!calanques | Marseille 43.30,5.37
!lappland | Narvik 68.44,17.43 ; Tromsø 69.65,18.96 ; Oslo 59.91,10.75 ; Karasjok 69.47,25.50
!lyngen | Tromsø 69.65,18.96
!hoher-atlas | Marrakesch 31.63,-8.00
!annapurna | Pokhara 28.21,83.99
!kilimandscharo | Moshi -3.35,37.34
!neuseeland-sued | Wellington -41.29,174.78 ; Auckland -36.85,174.76
!kleine-karpaten | Bratislava 48.146,17.107
!reunion | Mauritius -20.16,57.50
!mafate | Cilaos -21.135,55.47 ; Salazie -21.03,55.54 ; Saint-Denis -20.88,55.45
!la-gomera | Teide 28.27,-16.64
!teneriffa | Vallehermoso 28.18,-17.27 ; Tejeda 27.99,-15.62
!la-palma | Teide 28.27,-16.64
!gran-canaria | Teide 28.27,-16.64
!mallorca | Menorca 39.89,4.26 ; Ibiza 38.91,1.43
!ruegen | Stralsund 54.31,13.09
!osttirol | Sexten 46.70,12.35 ; Innichen 46.735,12.28 ; Kitzbühel 47.45,12.39 ; Lofer 47.59,12.70 ; Oberdrauburg 46.75,12.97 ; Bruneck 46.80,11.94
!villgratental | Sexten 46.70,12.35 ; Lienz 46.83,12.77 ; Kartitsch 46.74,12.50
!innsbruck | Kitzbühel 47.45,12.39 ; Schwaz 47.34,11.71 ; Mayrhofen 47.16,11.86 ; Neustift 47.11,11.32
!tuxer | Kitzbühel 47.45,12.39 ; Neustift 47.11,11.32
!brandnertal | Schruns 47.08,9.91 ; Feldkirch 47.24,9.60
!raetikon | Bregenz 47.50,9.75 ; Schruns 47.08,9.91
!wachau | St. Pölten 48.20,15.63 ; Wien 48.21,16.37
!neusiedlersee | Eisenstadt 47.85,16.52 ; Wien 48.21,16.37
!villach | Klagenfurt 46.62,14.31 ; Spittal an der Drau 46.80,13.49
!oetscher | Mariazell 47.77,15.32 ; Scheibbs 48.00,15.17
!peloponnes | Athen 37.98,23.73 ; Megara 37.99,23.34 ; Delphi 38.48,22.50 ; Nafpaktos 38.39,21.83 ; Kythira 36.20,22.99 ; Zakynthos 37.78,20.90 ; Aegina 37.74,23.43 ; Mesolongi 38.37,21.43 ; Hydra 37.35,23.46
!messenien | Sparta 37.07,22.43 ; Patras 38.25,21.73 ; Olympia 37.64,21.63 ; Gytheio 36.76,22.57
!argolis | Korinth 37.94,22.93 ; Tripoli 37.51,22.37
!ilia | Patras 38.25,21.73 ; Kalamata 37.04,22.11
!bodensee | Freiburg 47.99,7.85 ; Kempten 47.73,10.31
!wienerwald | Wien Stephansplatz 48.21,16.37 ; Reichenau 47.69,15.85 ; St. Pölten 48.20,15.63
!pitztal | Sölden 46.97,11.01 ; Landeck 47.14,10.57
!lesachtal | Lienz 46.83,12.77 ; Sillian 46.75,12.42
!seefeld | Innsbruck 47.26,11.39 ; Garmisch 47.49,11.09
!gastein | Zell am See 47.32,12.80 ; Mallnitz 46.98,13.17
!moelltal | Heiligenblut 47.04,12.84 ; Spittal 46.80,13.49
!millstaettersee | Spittal an der Drau 46.80,13.49
!grazer-hausberge | Leibnitz 46.78,15.54 ; Weiz 47.22,15.62
!oststeiermark | Graz 47.07,15.44 ; Bad Radkersburg 46.68,15.99 ; Oberwart 47.29,16.21
!kalkalpen | Admont 47.57,14.46 ; Steyr 48.04,14.42
!glarnerland | Chur 46.85,9.53 ; Zürich 47.37,8.54 ; Flims 46.83,9.28
!zuerichsee | Luzern 47.05,8.31 ; Winterthur 47.50,8.72
!genfersee | Bern 46.95,7.45 ; Sion 46.23,7.36
!vierwaldstaettersee | Engelberg 46.82,8.41 ; Interlaken 46.69,7.86
!emmental | Bern 46.95,7.45 ; Luzern 47.05,8.31 ; Thun 46.76,7.63
!gruyere | Montreux 46.43,6.91 ; Interlaken 46.69,7.86
!surselva | Chur 46.85,9.53 ; Andermatt 46.63,8.59 ; Davos 46.80,9.84
!davos | Arosa 46.78,9.68 ; Chur 46.85,9.53 ; Landquart 46.97,9.55
!vinschgau | Landeck 47.14,10.57 ; Meran 46.67,11.16
!meran | Bozen 46.50,11.35 ; Schlanders 46.63,10.77
!bozen | Meran 46.67,11.16 ; Trient 46.07,11.12 ; Seis 46.54,11.56
!sterzing | Brixen 46.72,11.66 ; Innsbruck 47.26,11.39 ; Steinach am Brenner 47.10,11.46
!ahrntal | Bruneck 46.80,11.94 ; Mayrhofen 47.16,11.86
!antholz | Bruneck 46.80,11.94 ; Sexten 46.70,12.35 ; Innichen 46.735,12.28
!pustertal | Brixen 46.72,11.66 ; Sexten 46.70,12.35
!seiser-alm | Bozen 46.50,11.35 ; Ortisei 46.57,11.67
!groeden | Seis 46.54,11.56 ; Corvara 46.55,11.87 ; Canazei 46.48,11.77
!fassatal | Bozen 46.50,11.35 ; Cortina 46.54,12.14 ; Arabba 46.50,11.88
!gadertal | Bruneck 46.80,11.94 ; Cortina 46.54,12.14
!sextner | Cortina 46.54,12.14 ; Bruneck 46.80,11.94
!cortina | Sexten 46.70,12.35 ; Corvara 46.55,11.87 ; Canazei 46.48,11.77
!eggental | Bozen 46.50,11.35 ; Canazei 46.48,11.77
!lago-maggiore | Mailand 45.46,9.19 ; Domodossola 46.12,8.29 ; Bellinzona 46.19,9.02
!comer-see | Mailand 45.46,9.19 ; Sondrio 46.17,9.87 ; Lugano 46.00,8.95
!adamello | Madonna di Campiglio 46.23,10.83 ; Bormio 46.47,10.37 ; Brescia 45.54,10.22
!vizentiner | Vicenza 45.55,11.55 ; Trient 46.07,11.12 ; Verona 45.44,10.99 ; Rovereto 45.89,11.04
!golf-neapel | Salerno 40.68,14.77 ; Caserta 41.07,14.33
!galicien | Oviedo 43.36,-5.85 ; Porto 41.15,-8.61 ; Soajo 41.87,-8.30 ; Braga 41.55,-8.43 ; Gijón 43.54,-5.66 ; León 42.60,-5.57 ; Chaves 41.74,-7.47
!kantabrien | Bilbao 43.26,-2.93 ; Oviedo 43.36,-5.85 ; Covadonga 43.31,-5.06 ; Llanes 43.42,-4.75
!asturien | Santander 43.46,-3.81 ; Potes 43.15,-4.62 ; Lugo 43.01,-7.56 ; León 42.60,-5.57 ; Fuente Dé 43.15,-4.81
!baskenland | Santander 43.46,-3.81 ; Pamplona 42.82,-1.64 ; Pau 43.30,-0.37 ; Burgos 42.34,-3.70
!costa-brava | Barcelona 41.39,2.17 ; Perpignan 42.70,2.90
!costa-daurada | Barcelona 41.39,2.17 ; Valencia 39.47,-0.38 ; Lleida 41.62,0.62
!costa-blanca | Valencia 39.47,-0.38 ; Murcia 37.99,-1.13 ; Cartagena 37.60,-0.99 ; Albacete 38.99,-1.86
!alentejo | Lagos 37.10,-8.67 ; Lissabon 38.72,-9.14 ; Faro 37.02,-7.93 ; Badajoz 38.88,-6.97 ; Sevilla 37.39,-5.99
!nordportugal | Lissabon 38.72,-9.14 ; Coimbra 40.21,-8.43 ; Vigo 42.24,-8.72 ; Ourense 42.34,-7.86
!korfu | Igoumenitsa 39.50,20.27 ; Paxos 39.20,20.18
!chalkidiki | Thessaloniki 40.64,22.94 ; Olymp 40.09,22.36 ; Limenas 40.78,24.71 ; Kavala 40.94,24.41
!thassos | Kavala 40.94,24.41 ; Athos 40.16,24.33
!olymp | Thessaloniki 40.64,22.94 ; Larisa 39.64,22.42 ; Katerini 40.27,22.50
!pilion | Larisa 39.64,22.42 ; Skiathos 39.16,23.49 ; Lamia 38.90,22.43
!kefalonia | Vathy Ithaka 38.37,20.72 ; Zakynthos 37.78,20.90 ; Lefkada 38.71,20.64
!ithaka | Argostoli 38.18,20.49 ; Sami 38.25,20.65
!zakynthos | Kyllini 37.93,21.15 ; Poros Kefalonia 38.15,20.77
!samos | Agios Kirykos 37.61,26.30 ; Kusadasi 37.86,27.26 ; Patmos 37.31,26.55
!ikaria | Karlovasi 37.79,26.70
!patmos | Leros 37.15,26.85 ; Pythagoreio 37.69,26.94
!fourni | Agios Kirykos 37.61,26.30 ; Pythagoreio 37.69,26.94 ; Patmos 37.31,26.55
!dovrefjell | Oppdal 62.60,9.69 ; Rondvassbu 61.92,10.00 ; Lillehammer 61.11,10.47
!vesteraalen | Svolvær 68.23,14.57 ; Harstad 68.80,16.54 ; Narvik 68.44,17.43
!gotland | Borgholm 56.88,16.65 ; Stockholm 59.33,18.07
!oeland | Kalmar 56.66,16.36 ; Visby 57.64,18.30
!bornholm | Simrishamn 55.56,14.35 ; Kopenhagen 55.68,12.57
!faeroeer | Reykjavik 64.15,-21.94 ; Lerwick 60.15,-1.15
!kanalinseln | Saint-Malo 48.65,-2.02 ; Cherbourg 49.64,-1.62
!devon | Truro 50.26,-5.05 ; Bude 50.83,-4.54 ; Bath 51.38,-2.36 ; Dorchester 50.71,-2.44 ; Lyme Regis 50.73,-2.93
!molokai | Lahaina 20.88,-156.68 ; Honolulu 21.31,-157.86
!cote-d-azur | Marseille 43.30,5.37 ; Ventimiglia 43.79,7.61 ; Toulon 43.12,5.93 ; Digne 44.09,6.24
!burgund | Paris 48.86,2.35 ; Lyon 45.76,4.84 ; Besançon 47.24,6.02 ; Orléans 47.90,1.91
!dordogne | Bordeaux 44.84,-0.58 ; Toulouse 43.60,1.44 ; Limoges 45.83,1.26 ; Clermont-Ferrand 45.78,3.09
!dauphine | Lyon 45.76,4.84 ; Chambéry 45.57,5.92 ; Avignon 43.95,4.81 ; Annecy 45.90,6.13 ; Digne 44.09,6.24
!tasmanien | Melbourne -37.81,144.96 ; Wilsons Promontory -39.03,146.32
"""


def _teile(txt):
    out = []
    for zeile in txt.strip().splitlines():
        if zeile.startswith("#"):
            continue
        kopf, rest = zeile.split(" | ", 1)
        neg = kopf.startswith("!")
        for p in rest.split(" ; "):
            name, koord = p.rsplit(" ", 1)
            la, ln = koord.split(",")
            out.append((kopf.lstrip("!"), name, float(la), float(ln), neg))
    return out


PUNKTE = _teile(POS) + _teile(NEG)
