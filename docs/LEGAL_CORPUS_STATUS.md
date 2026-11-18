# Pokrytie autentického právneho korpusu

V overenej lokálnej databáze je **1 slovenský predpis, 2 archivované časové znenia, 123 paragrafov a 5 článkov základných zásad v každom znení, 816 indexovaných pasáží a 0 rozhodnutí**. Import indexuje čl. I zákona č. 36/2005 Z. z. Archív obsahuje celé pôvodné HTML. Novelizačné články II až VIII, poznámky pod čiarou a prílohy sú mimo indexu. Čísla platia pre tento lokálny import, prázdna aplikácia databázu automaticky neplní.

| Znenie | Interval účinnosti vrátane prvého aj posledného dňa | Index | Zdroj |
| --- | --- | --- | --- |
| `sk-zz-2005-36-20250801` | 2025-08-01 až 2026-05-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20250801.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20250801.pdf) |
| `sk-zz-2005-36-20260601` | 2026-06-01 až 2026-08-31 | 408 pasáží | [HTML](https://static.slov-lex.sk/static/SK/ZZ/2005/36/20260601.print.html) · [záväzný PDF](https://static.slov-lex.sk/pdf/SK/ZZ/2005/36/ZZ_2005_36_20260601.pdf) |

Oficiálne HTML je informatívne. Dátumy zobrazené v jeho hlavičke sa zhodovali s hlavičkou príslušného PDF. V SQLite je koniec intervalov prvý vylúčený deň. Pri dopyte `36/2005 § 4 ods. 2` sa 31. mája 2026 našlo staršie znenie a 1. júna 2026 novšie. Dopyty pred prvým pokrytým dňom a po poslednom pokrytom dni správne nedostali znenie z tohto korpusu. Paragrafy 114 až 119b sú označené ako prechodné. Získanie oficiálneho exportu, kontrola integrity a správne hranice intervalov sú oddelené od odborného posúdenia prípadu.

## Opakovateľný offline import

Uložte oba presné HTML exporty z tabuľky mimo Gitu. Z koreňa repozitára spustite:

```powershell
uv run --locked --offline python -m scripts.import_slovlex 20250801 .tm-law/sources/36-20250801.html
uv run --locked --offline python -m scripts.import_slovlex 20260601 .tm-law/sources/36-20260601.html
uv run --locked --offline python -m scripts.legal_corpus --data-dir .tm-law/slovlex coverage
```

Import nevyžaduje sieť a pri odlišných bajtoch skončí pred zápisom do databázy. SHA-256 a dátumy pôvodného získania sú v [katalógu importéra](../scripts/import_slovlex.py). Na použitie korpusu v aplikácii zadajte spúšťaču `-DataDir .tm-law/slovlex` alebo nastavte `TM_LAW_DATA_DIR`. Právny text predpisov má osobitný režim podľa [§ 5 písm. b) Autorského zákona](https://www.slov-lex.sk/ezbierky/pravne-predpisy/SK/ZZ/2015/185/20260901). Podmienky ďalších exportov a rozhodnutí treba preverovať osobitne.
