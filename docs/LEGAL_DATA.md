# Právne dáta

MVP importuje jeden UTF-8 JSON súbor na znenie, cez web alebo modul `scripts.import_legal`. Schému možno použiť pre slovenské zákony, rozhodnutia a právo EÚ. Úseky sa pripravujú mimo aplikácie, podľa pôvodného číslovania. Pri rozhodnutiach zaznamenajte súd, spisovú značku a dátum, ak sú potvrdené.

Použite [demo-2022.json](../data/demo-2022.json) ako syntetický príklad tvaru súboru. Pre reálne znenie uveďte URL pôvodného vydania alebo verzie, orgán, dátum získania, pôvod a podmienky ďalšieho použitia. Ak máte originálne bajty súboru, `original_sha256` môže uchovať ich 64-znakový SHA-256. Import overuje formát poľa a vypočíta samostatný `content_sha256` z normalizovaných importovaných údajov. Originálny súbor sa neoveruje a neukladá spolu s JSON.

- `version_id` označuje konkrétne znenie. `source_id` je jedinečný v rámci znenia. Spolu tvoria identifikátor `version_id/source_id`.
- `published_on` uchováva známy dátum vyhlásenia. `effective_from` a `effective_until` určujú účinnosť.
- `effective_from` je zahrnutý, `effective_until` je prvý deň mimo účinnosti. Neznáme dátumy nastavte na `null`.
- `open_ended: true` použite len pri doloženom otvorenom intervale. Úsek s neznámym začiatkom alebo neznámym koncom bez potvrdeného otvoreného intervalu sa pri dátumovom vyhľadávaní predpisov nezahrnie. Pri rozhodnutiach môže filter použiť dátum rozhodnutia.
- `section`, `paragraph` a `letter` obsahujú označenia bez prefixov, napríklad `7`, `2` a `a`.

FTS5 podporuje bezdiakritické vyhľadávanie, hľadanie podľa čísla predpisu v tvare `číslo/rok` a podľa `§`. Viac explicitných odkazov sa spracuje len vtedy, keď sú oddelené bodkočiarkou a každý úsek má najviac jeden predpis a najviac jeden `§` alebo `Čl.`. Podporované sú napríklad `9999/2099 § 7; 9998/2099 § 2` a `9999/2099 § 7; § 2`. Ak je v dopyte jediné číslo predpisu, použije sa aj pre úsek, ktorý uvádza len paragraf. Každý úsek dostane rovnaký rozhodujúci dátum, filter fiktívnych záznamov a limit; výsledky sa spoja bez duplicít tak, aby prvý odkaz nezabral celý dostupný limit. Text bez bodkočiarky zostáva jeden dopyt a použije len prvý explicitný odkaz. Aplikácia negarantuje pokrytie predmetnej veci, neidentifikuje prechodné ustanovenia a neodvodzuje účinnosť z dátumu vyhlásenia. Právnu pôsobnosť musí právnik posúdiť aj podľa skutkového stavu. Otvorené intervaly upravte podľa nových doložených údajov pri príprave korpusu. MVP neposkytuje editor ani mazanie verejnej zbierky. Na opravu problematického korpusu odporúčame vytvoriť nový dátový adresár a importovať opravený súbor znení.

## Import balíka s pôvodným dokumentom

CLI `scripts.legal_corpus` pracuje offline. Z oficiálneho zdroja najprv uložte konkrétne znenie ako UTF-8 TXT, HTML, XML alebo PDF s textovou vrstvou. Vedľa originálu vytvorte manifest podľa [fiktívnej ukážky](../data/corpus-example/manifest.json). Príkaz `draft` vygeneruje SHA-256 a navrhne hranice článkov, paragrafov a odsekov v číslovanom texte. Výstup pred importom skontrolujte, doplňte pôvod dokumentu a dátumy. HTML/XML sa spracúva ako text, externé zdroje sa nenačítajú.

```powershell
uv run --locked python -m scripts.legal_corpus draft data/corpus-example/synthetic.txt
uv run --locked python -m scripts.legal_corpus validate data/corpus-example/manifest.json
uv run --locked python -m scripts.legal_corpus --data-dir .tm-law/demo-corpus import data/corpus-example/manifest.json
uv run --locked python -m scripts.legal_corpus --data-dir .tm-law/demo-corpus coverage
```

Manifest vyžaduje `acquired_at` s časovou zónou a pri známom začiatku účinnosti aj textový `effective_basis`. Pole `valid_from` a `valid_until` eviduje platnosť oddelene od účinnosti. Články sa ukladajú ako `cl-1` a vyhľadávajú ako `Čl. 1`. Voliteľné `norm_status` umožňuje označiť prechodné alebo zrušené ustanovenie. Dátumový filter nenahrádza posúdenie prechodných ustanovení. Pri rozhodnutí sa eviduje typ rozhodnutia, stav publikovania alebo anonymizácie a voliteľné citované predpisy.

Import porovná deklarovaný SHA-256 s bajtmi originálu a overí prítomnosť vybraných pasáží s toleranciou medzier a normalizácie Unicode. Originál archivuje v samostatnej SQLite tabuľke a pasáže indexuje transakčne. Opakovaný import rovnakého znenia zostane bez duplicity. `export-original SHA CESTA` overí integritu a zapíše originál do nového súboru. `coverage` odlíši fiktívne znenia, znenia bez archivovaného podkladu a znenia s archivovanými bajtmi. Kontrola integrity sama nepotvrdzuje autoritu zdroja. Databáza schémy 1 sa automaticky migruje na schému 2.

Pribalené sú iba fiktívne testovacie dáta. [Zdroje, obmedzenia prístupu a presné pokrytie](LEGAL_SOURCES.md).

Projekt má licenciu MIT. Importovaný obsah a modelové váhy majú vlastné podmienky použitia, ktoré treba zaznamenať a preveriť pred ďalšou distribúciou.

Pred použitím importovaných znení v hodnotení spustite kontrolu benchmarkových referencií. Overí, či očakávaný identifikátor má lokálny archivovaný podklad a či znenie pokrýva rozhodujúci dátum z úlohy. [Kontrola referencií pred inferenciou](BENCHMARKS.md#kontrola-referencií-pred-inferenciou).
