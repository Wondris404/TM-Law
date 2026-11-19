# Pokrytie autentického právneho korpusu

V cloudovej databáze sa overili **3 slovenské predpisy, 6 archivovaných časových znení a 2 730 indexovaných pasáží**. Korpus zatiaľ neobsahuje rozhodnutia. Prázdna aplikácia databázu automaticky neplní.

## Zákon č. 36/2005 Z. z.

Zákon o rodine má **3 archivované časové znenia, 123 paragrafov a 5 článkov základných zásad v každom znení a 1 225 indexovaných pasáží**. Import indexuje čl. I. Archív obsahuje celé pôvodné HTML. Novelizačné články II až VIII, poznámky pod čiarou a prílohy sú mimo indexu.

| Znenie | Interval účinnosti vrátane prvého aj posledného dňa | Index | Zdroj |
| --- | --- | --- | --- |
| `sk-zz-2005-36-20250801` | 2025-08-01 až 2026-05-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20250801.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20250801.pdf) |
| `sk-zz-2005-36-20260601` | 2026-06-01 až 2026-08-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20260601.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20260601.pdf) |
| `sk-zz-2005-36-20260901` | 2026-09-01 až 2026-12-31 | 409 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20260901.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20260901.pdf) |

Oficiálne HTML je informatívne. Dátumy zobrazené v jeho hlavičke sa zhodovali s hlavičkou príslušného PDF. V SQLite je koniec intervalov prvý vylúčený deň. Pri dopyte `36/2005 § 4 ods. 2` sa 31. mája 2026 našlo staršie znenie a 1. júna 2026 novšie. Dopyt na `36/2005 § 91 ods. 2` od 1. septembra 2026 vyberá nové znenie. Paragrafy 114 až 119b sú označené ako prechodné. Záväzný PDF septembrového znenia mal pri získaní SHA-256 `9dfaeca19f554909561c50ffdb3cc996e45cc504d914e717909dbc4a768fc73a`.

## Ústava č. 460/1992 Zb.

Obe archivované znenia spolu majú **1 250 pasáží**. Každé obsahuje úvodnú preambulu `predpis.text` bez čísla článku. Staršie znenie má 176 článkov, novšie 177 článkov. `norm_status` nie je vyplnené. Najdlhší text pasáže má 901 znakov. Schéma `LegalVersion` povoľuje najviac 800 pasáží v jednom znení.

| Znenie | Interval účinnosti vrátane prvého aj posledného dňa | Index | Zdroj |
| --- | --- | --- | --- |
| `sk-zz-1992-460-20250101` | 2025-01-01 až 2025-10-31 | 621 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/1992/460/20250101.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/1992/460/ZZ_1992_460_20250101.pdf) |
| `sk-zz-1992-460-20251101` | Od 2025-11-01 | 629 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/1992/460/20251101.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/1992/460/ZZ_1992_460_20251101.pdf) |

Pri prvom znení majú hlavičky HTML a PDF zhodný začiatok a koniec účinnosti. `published_on` je dátum vyhlásenia 1992-10-01. V SQLite má staršie znenie `effective_until=2025-11-01`. Novšie znenie má podľa hlavičiek HTML a PDF začiatok 2025-11-01 a otvorený koniec. Riadok 29 histórie znení v HTML potvrdzuje otvorený interval.

HTML samo uvádza, že zobrazený obsah je informatívny a právne záväzný obsah je v PDF. Import archivuje bajty HTML. PDF je v katalógu pripnuté adresou a SHA-256 a v SQLite nie je druhý originál. SHA-256 HTML je `f58fc284e6aea0c3905d1b8f8d92e424fa9584a58b5b830565255b7414999fa1` (654446 bajtov). SHA-256 PDF je `010bca4e5da12a25029384b62c29b422de17e7da87fb1dc33b2ce7dfef36dad0` (624923 bajtov, 45 strán). Oba súbory prišli obyčajným verejným GET so stavom 200 dňa 2026-11-19 o 09:00:06 UTC. Opakovaný GET HTML s `Accept-Encoding: identity` o 09:11:51 UTC vrátil tie isté bajty. Hlavička `content-md5` odpovede HTML sa s MD5 týchto bajtov nezhoduje, preto sa na kontrolu použil SHA-256 uloženého tela. `content-md5` PDF sa s bajtami PDF zhoduje. `acquired_at` je `2026-11-19T09:00:06+00:00`.

Index berie preambulu a uzly `ustavnyclanok-*.text`. Súrodenec `text2` sa pripája k tej istej pasáži. Vnorené citáty sa stávajú súčasťou pasáže a nadpisy hláv a oddielov zostávajú mimo indexu.

Dopyt `460/1992 Čl. 7 ods. 7` pred 1. novembrom 2025 nedostal odsek. Od 1. novembra ho našiel iba v znení `sk-zz-1992-460-20251101`.

## Správny poriadok č. 71/1967 Zb.

Znenie `sk-zz-1967-71-20180901` obsahuje **85 paragrafov a 255 pasáží**. Hlavičky HTML a PDF uvádzajú začiatok 1. septembra 2018 a otvorený koniec. Import zachováva číslovanie odsekov a bodov a označuje § 82 a § 84 ako prechodné. Dopyt `71/1967 § 54 ods. 1; ods. 2` vrátil oba odseky pre 1. november 2025. Pri dopyte na § 54 ods. 2 k 31. augustu 2018 nebol v korpuse podklad. [HTML](https://static.slov-lex.sk/static/SK/ZZ/1967/71/20180901.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/1967/71/ZZ_1967_71_20180901.pdf)

## Opakovateľný offline import

Uložte presné HTML exporty z tabuliek mimo Gitu. Z koreňa repozitára spustite:

```powershell
uv run --locked --offline python -m scripts.import_slovlex 20250801 .tm-law/sources/36-20250801.html
uv run --locked --offline python -m scripts.import_slovlex 20260601 .tm-law/sources/36-20260601.html
uv run --locked --offline python -m scripts.import_slovlex 20260901 .tm-law/sources/36-20260901.html
uv run --locked --offline python -m scripts.import_slovlex 20250101 .tm-law/sources/460-20250101.html
uv run --locked --offline python -m scripts.import_slovlex 20251101 .tm-law/sources/460-20251101.html
uv run --locked --offline python -m scripts.import_slovlex 20180901 .tm-law/sources/71-20180901.html
uv run --locked --offline python -m scripts.legal_corpus --data-dir .tm-law/slovlex coverage
```

Import je offline a pri odlišných bajtoch skončí pred zápisom do databázy. SHA-256 HTML a časy pôvodného získania sú v katalógu importéra. Originály uložte mimo Gitu. Na použitie korpusu v aplikácii zadajte spúšťaču `-DataDir .tm-law/slovlex` alebo nastavte `TM_LAW_DATA_DIR`. Právny text predpisov má osobitný režim podľa § 5 písm. b) Autorského zákona. [Katalóg importéra](../scripts/import_slovlex.py) · [Autorský zákon](https://www.slov-lex.sk/ezbierky/pravne-predpisy/SK/ZZ/2015/185/20260901)

V korpuse naďalej chýbajú predpisy **162/2015, 40/1964, 160/2015, 161/2015, 300/2005, 301/2005, 513/1991 a 311/2001**, ostatné časové znenia troch načítaných predpisov a judikatúra.
