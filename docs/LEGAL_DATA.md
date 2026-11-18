# Právne dáta

MVP importuje jeden UTF-8 JSON súbor na znenie, cez web alebo modul `scripts.import_legal`. Schému možno použiť pre slovenské zákony, rozhodnutia a právo EÚ. Úseky sa pripravujú mimo aplikácie, podľa pôvodného číslovania. Pri rozhodnutiach zaznamenajte súd, spisovú značku a dátum, ak sú potvrdené.

Použite [demo-2022.json](../data/demo-2022.json) ako syntetický príklad tvaru súboru. Pre reálne znenie uveďte URL pôvodného vydania alebo verzie, orgán, dátum získania, pôvod a podmienky ďalšieho použitia. Ak máte originálne bajty súboru, `original_sha256` môže uchovať ich 64-znakový SHA-256. Import overuje formát poľa a vypočíta samostatný `content_sha256` z normalizovaných importovaných údajov. Originálny súbor sa neoveruje a neukladá spolu s JSON.

- `version_id` označuje konkrétne znenie. `source_id` je jedinečný v rámci znenia. Spolu tvoria identifikátor `version_id/source_id`.
- `published_on` uchováva známy dátum vyhlásenia. `effective_from` a `effective_until` určujú účinnosť.
- `effective_from` je zahrnutý, `effective_until` je prvý deň mimo účinnosti. Neznáme dátumy nastavte na `null`.
- `open_ended: true` použite len pri doloženom otvorenom intervale. Úsek s neznámym začiatkom alebo neznámym koncom bez potvrdeného otvoreného intervalu sa pri dátumovom vyhľadávaní predpisov nezahrnie. Pri rozhodnutiach môže filter použiť dátum rozhodnutia.
- `section`, `paragraph` a `letter` obsahujú označenia bez prefixov, napríklad `7`, `2` a `a`.

FTS5 podporuje bezdiakritické vyhľadávanie, hľadanie podľa čísla predpisu v tvare `číslo/rok` a podľa `§`. Aplikácia negarantuje pokrytie predmetnej veci, neidentifikuje prechodné ustanovenia a neodvodzuje účinnosť z dátumu vyhlásenia. Právnu pôsobnosť musí právnik posúdiť aj podľa skutkového stavu. Otvorené intervaly upravte podľa nových doložených údajov pri príprave korpusu. MVP neposkytuje editor ani mazanie verejnej zbierky. Na opravu problematického korpusu odporúčame vytvoriť nový dátový adresár a importovať opravený súbor znení.

Pribalené sú iba fiktívne testovacie dáta. Prístup k Slov-Lexu z vývojového cloudu v tomto behu vrátil 403 a žiadny text odtiaľ sa neimportoval. Aplikácia neobsahuje sťahovač ani zdrojové API konektory. Pre ďalšiu fázu overte spôsob prístupu, podmienky a potrebnú anonymizáciu pre každý zdroj:

- Predpisy a historické znenia na [Slov-Lexe](https://www.slov-lex.sk/) a [EUR-Lexe](https://eur-lex.europa.eu/).
- Judikatúra na [Najvyššom súde SR](https://www.nsud.sk/), [Najvyššom správnom súde SR](https://www.nssud.sk/), [Ústavnom súde SR](https://www.ustavnysud.sk/), [Ministerstve spravodlivosti SR](https://www.justice.gov.sk/) a v [HUDOC](https://hudoc.echr.coe.int/).

Projekt má licenciu MIT. Importovaný obsah a modelové váhy majú vlastné podmienky použitia, ktoré treba zaznamenať a preveriť pred ďalšou distribúciou.
