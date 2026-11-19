# Pokrytie autentického právneho korpusu

V spoločnej lokálnej databáze sa overili **2 slovenské predpisy, 3 archivované časové znenia, 1 437 indexovaných pasáží a 0 rozhodnutí**. Na spoločnom dátume 31. októbra 2025 vyhľadávanie vrátilo pasáže z oboch predpisov. Osem benchmarkových referencií zákona o rodine znovu prešlo kontrolou archívu. Prázdna aplikácia databázu automaticky neplní.

## Zákon č. 36/2005 Z. z.

Zákon o rodine má **2 archivované časové znenia, 123 paragrafov a 5 článkov základných zásad v každom znení, 816 indexovaných pasáží a 0 rozhodnutí**. Opakovaný import do spoločnej databázy použil pôvodné `version_id`. Import indexuje čl. I. Archív obsahuje celé pôvodné HTML. Novelizačné články II až VIII, poznámky pod čiarou a prílohy sú mimo indexu.

| Znenie | Interval účinnosti vrátane prvého aj posledného dňa | Index | Zdroj |
| --- | --- | --- | --- |
| `sk-zz-2005-36-20250801` | 2025-08-01 až 2026-05-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20250801.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20250801.pdf) |
| `sk-zz-2005-36-20260601` | 2026-06-01 až 2026-08-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20260601.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20260601.pdf) |

Oficiálne HTML je informatívne. Dátumy zobrazené v jeho hlavičke sa zhodovali s hlavičkou príslušného PDF. V SQLite je koniec intervalov prvý vylúčený deň. Pri dopyte `36/2005 § 4 ods. 2` sa 31. mája 2026 našlo staršie znenie a 1. júna 2026 novšie. Dopyty pred prvým pokrytým dňom a po poslednom pokrytom dni správne nedostali znenie z tohto korpusu. Paragrafy 114 až 119b sú označené ako prechodné. Získanie oficiálneho exportu, kontrola integrity a správne hranice intervalov sú oddelené od odborného posúdenia prípadu.

## Ústava č. 460/1992 Zb.

Overený import `sk-zz-1992-460-20250101` má **1 archivované HTML, 621 pasáží a 176 článkov**. Jedna pasáž je preambula `predpis.text` bez čísla článku. Zvyšných 620 pasáží patrí článkom. Spoločná databáza obsahuje jedno znenie ústavy. `norm_status` nie je vyplnené. Najdlhší text pasáže má 901 znakov. Schéma `LegalVersion` povoľuje najviac 800 pasáží v jednom znení.

| Znenie | Interval účinnosti vrátane prvého aj posledného dňa | Index | Zdroj |
| --- | --- | --- | --- |
| `sk-zz-1992-460-20250101` | 2025-01-01 až 2025-10-31 | 621 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/1992/460/20250101.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/1992/460/ZZ_1992_460_20250101.pdf) |

Tlačové HTML má v hlavičke text „Časová verzia predpisu účinná od 01.01.2025 do 31.10.2025“ a atribúty `data-from="2025-01-01"` a `data-to="2025-10-31"`. Informačná tabuľka uvádza názov „Ústava Slovenskej republiky“, autora „Slovenská národná rada“, dátum schválenia 01.09.1992 a dátum vyhlásenia 01.10.1992. Prvá strana PDF uvádza „Vyhlásené: 1. 10. 1992“ a „Časová verzia predpisu účinná od: 1. 1.2025 do: 31.10.2025“. `published_on` je dátum vyhlásenia 1992-10-01. V SQLite je `effective_until` 2025-11-01. Riadok 28 histórie v tom istom HTML je „01.01.2025 - 31.10.2025“. Riadok 29 je „01.11.2025 -“ a `data-ucinnostdo` je prázdne; toto otvorené znenie import neobsahuje.

HTML samo uvádza, že zobrazený obsah je informatívny a právne záväzný obsah je v PDF. Import archivuje bajty HTML. PDF je v katalógu pripnuté adresou a SHA-256 a v SQLite nie je druhý originál. SHA-256 HTML je `f58fc284e6aea0c3905d1b8f8d92e424fa9584a58b5b830565255b7414999fa1` (654446 bajtov). SHA-256 PDF je `010bca4e5da12a25029384b62c29b422de17e7da87fb1dc33b2ce7dfef36dad0` (624923 bajtov, 45 strán). Oba súbory prišli obyčajným verejným GET so stavom 200 dňa 2026-11-19 o 09:00:06 UTC. Opakovaný GET HTML s `Accept-Encoding: identity` o 09:11:51 UTC vrátil tie isté bajty. Hlavička `content-md5` odpovede HTML sa s MD5 týchto bajtov nezhoduje, preto sa na kontrolu použil SHA-256 uloženého tela. `content-md5` PDF sa s bajtami PDF zhoduje. `acquired_at` je `2026-11-19T09:00:06+00:00`.

Index berie preambulu a uzly `ustavnyclanok-*.text`. Súrodenec `text2` sa pripája k tej istej pasáži pri článkoch 75 ods. 1, 104 ods. 1, 112 ods. 1 a 134 ods. 5. Vnorený citát nie je samostatná pasáž. Nadpisy hláv a oddielov sa neindexujú. Číselné identifikátory článkov v exporte sú 1 až 156 okrem 11 a 132. Ďalšie sú 7a, 39a, 55a, 64a, 81a, 88a, 125a, 125b, 127a, 129a, 141a, 141b, 145a, 151a, 154a, 154b, 154c, 154d, 154e, 154f, 154g a 154h. Spolu je to 176 článkov a 620 článkových pasáží.

Dopyt `460/1992 Čl. 1 ods. 1` vrátil `sk-zz-1992-460-20250101/ustavnyclanok-1.odsek-1` pre dni 2025-01-01, 2025-06-01 a 2025-10-31. Pre dni 2024-12-31 a 2025-11-01 nevrátil nič. Opakovaný import toho istého HTML vrátil `created: false`. Táto kontrola nepotvrdzuje právnu správnosť textu.

## Opakovateľný offline import

Uložte presné HTML exporty z tabuliek mimo Gitu. Z koreňa repozitára spustite:

```powershell
uv run --locked --offline python -m scripts.import_slovlex 20250801 .tm-law/sources/36-20250801.html
uv run --locked --offline python -m scripts.import_slovlex 20260601 .tm-law/sources/36-20260601.html
uv run --locked --offline python -m scripts.import_slovlex 20250101 .tm-law/sources/460-20250101.html
uv run --locked --offline python -m scripts.legal_corpus --data-dir .tm-law/slovlex coverage
```

Import nevyžaduje sieť a pri odlišných bajtoch skončí pred zápisom do databázy. SHA-256, adresy PDF a dátumy pôvodného získania sú v [katalógu importéra](../scripts/import_slovlex.py). HTML ústavy aj zákona o rodine patria mimo Git. Na použitie korpusu v aplikácii zadajte spúšťaču `-DataDir .tm-law/slovlex` alebo nastavte `TM_LAW_DATA_DIR`. Právny text predpisov má osobitný režim podľa [§ 5 písm. b) Autorského zákona](https://www.slov-lex.sk/ezbierky/pravne-predpisy/SK/ZZ/2015/185/20260901). Podmienky ďalších exportov a rozhodnutí treba preverovať osobitne.

V korpuse naďalej chýbajú predpisy **162/2015, 40/1964, 160/2015, 161/2015, 300/2005, 301/2005, 513/1991 a 311/2001**, ďalšie znenia **36/2005**, ostatné časové znenia **460/1992** vrátane otvoreného intervalu od 2025-11-01 a judikatúra.
