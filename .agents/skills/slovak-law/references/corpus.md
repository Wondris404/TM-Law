# Rozširovanie korpusu a overovanie

Skill dáva modelu postup. Právne podklady prichádzajú z lokálnej databázy TM-Law. Pokrytie závisí od verzií, pasáží a rozhodnutí, ktoré konkrétna inštalácia naozaj importovala.

## Ako získať a importovať podklad

1. Urči právny problém, chýbajúcu pasáž a dátum. Na oficiálnom portáli otvor konkrétne časové znenie alebo rozhodnutie. Ulož originál, jeho adresu, vydávajúci orgán a čas získania s časovou zónou. Pri informatívnom HTML si dolož právne rozhodujúcu podobu osobitne a porovnaj kľúčové pasáže, prílohy a dátumy. Pri nezhode zaznamenaj rozsah a dôvod a over sporné tvrdenie v rozhodujúcom zdroji.
2. Pre predpis eviduj číslo a rok, dátum vyhlásenia, platnosť, účinnosť a dôvod zvoleného intervalu. Koniec účinnosti vlož ako prvý deň mimo intervalu. Neznámy dátum nechaj `null`. Použi `open_ended: true` len pri doloženom otvorenom konci. Pri postupnej účinnosti zaznamenaj rozdiely na úrovni relevantných ustanovení. Ak jeden interval v schéme nepokrýva všetky pasáže, navrhni odlíšené verzie alebo zdokumentuj medzeru pred použitím.
3. Pre rozhodnutie zachyť súd, spisovú značku, dátum, typ, stav zverejnenia a podľa možností citované predpisy. ECLI, stav neskoršieho preskúmania, prípadný preklad a zbierkové číslo eviduj v rešeršnom zázname. Dátum rozhodnutia a jeho právoplatnosť dokladaj samostatne. Zaznamenaj pôvod, podmienky opakovaného použitia a prípadné osobné údaje. Súkromné spisy drž oddelene od verejného korpusu.
4. Priprav manifest podľa [schémy a ukážky balíka](../../../../docs/LEGAL_DATA.md#import-balíka-s-pôvodným-dokumentom) s odkazom na originálny súbor a SHA-256. Skontroluj hranice paragrafu, odseku, písmena a bodu, najmä pri PDF, tabuľkách a vnorených citátoch. Dlhý predpis môže prekročiť limit 800 pasáží na `LegalVersion`. Naplánuj segmentáciu so stabilnými ID a s opisom rozsahu každej časti. Over, či vyhľadávanie zachová odkazy naprieč časťami a či report pokrytia nevydáva čiastkový záznam za celý predpis.
5. Over manifest, importuj do samostatného dátového adresára a skontroluj `coverage`. Ručne porovnaj vzorku s originálom vrátane posledného dňa starého a prvého dňa nového znenia. Prever opakovaný import a výsledok otázky mimo doloženého obdobia. Originály, databázu a výstupy s osobnými údajmi drž mimo Gitu. [Stav korpusu](../../../../docs/LEGAL_CORPUS_STATUS.md)

```sh
uv run --locked python -m scripts.legal_corpus draft .tm-law/sources/original.pdf
uv run --locked python -m scripts.legal_corpus validate .tm-law/sources/manifest.json
uv run --locked python -m scripts.legal_corpus --data-dir .tm-law/research import .tm-law/sources/manifest.json
uv run --locked python -m scripts.legal_corpus --data-dir .tm-law/research coverage
```

`draft` vytvorí návrh pasáží. Aktualizáciu rob znovu po overení novej verzie, s archivovaním skorších znení. Pri nedostupnom zdroji zaznamenaj dátum, adresu a rozsah medzery. Použi povolený verejný export, manuálny prístup alebo oficiálne poskytnutý balík. Pre hromadný prístup k Slov-Lexu a slovenským rozhodnutiam ostáva otvorené, aké rozhrania, pokrytie a podmienky poskytovatelia garantujú. EUR-Lex dokumentuje registrovanú webovú službu a pri veľkých objemoch CELLAR API alebo Data Dump. [Opakované použitie EUR-Lex](https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html?locale=en) · [Webová služba EUR-Lex](https://eur-lex.europa.eu/content/help/content/help/data-reuse/webservice.html)

## Poradie rozširovania

| Poradie | Čo zaradiť a ako overiť pokrytie |
| --- | --- |
| 1 | Doplň medzery, ktoré už hlási projekt. Začni 40/1964, 160/2015, 161/2015, 162/2015, 300/2005, 301/2005, 513/1991 a 311/2001. Pre každú vybranú tému pokry dátumy z existujúcich a plánovaných otázok, prechodné ustanovenia a súvisiace procesné pravidlá. Priprav 260/2026 s doloženým budúcim začiatkom účinnosti. [Pokrytie TM-Law](../../../../docs/LEGAL_CORPUS_STATUS.md) · [vyhlásený Občiansky zákonník](https://static.slov-lex.sk/pdf/SK/ZZ/2026/260/ZZ_2026_260.pdf) |
| 2 | K témam pridaj publikované rozhodnutia NS SR, NSS SR a ÚS SR. Zahrň aj prípady s opačným výsledkom pre odlišné fakty alebo verziu zákona. Vrstvu rozšír o rozhodnutia nižších súdov podľa potreby a eviduj medzery zverejňovania. |
| 3 | Doplň osobitné režimy podľa reálnych otázok, vykonávacie a miestne predpisy, právo EÚ a relevantnú judikatúru Súdneho dvora EÚ a ESĽP. Pokrytie vyhodnocuj podľa oblasti, časového rozpätia a typu zdroja. [Mapa prameňov](sources.md) |

## Ako zistiť, či skill zlepšil odpovede

Použi tú istú snímku korpusu, model a nastavenia na základnej vetve aj na vetve so skillom. Existujúce sady pokrývajú napríklad [rodinné právo](../../../../benchmarks/slovak-family-law.jsonl) a [medzery v korpuse](../../../../benchmarks/slovak-priority-gaps.jsonl). Pri autentických referenciách spusti audit pred inferenciou. Úlohy s novými zdrojmi pridaj po overení právnikom a oddeľ ich od tréningových príkladov. [Benchmarky a slepé právne hodnotenie](../../../../docs/BENCHMARKS.md)

| Kontrolná situácia | Očakávané správanie |
| --- | --- |
| Dopyt tesne pred a po zmene ustanovenia | Pre každý deň použije doložené znenie. Porovnanie vysvetlí vecný rozdiel a označí časové hranice. |
| Nový OZ vyhlásený s neskoršou účinnosťou | Oddelí vyhlásenie a účinnosť. Pri staršej zmluve preskúma režim podľa § 1893 a pri plynúcej lehote podľa § 1896. |
| Chýba doklad o doručení rozhodnutia | Vyžiada potrebný údaj alebo uvedie podmienený výpočet. Pri neistote neuvádza jediný pevný termín. |
| Rozhodnutie s inou skutkovou situáciou alebo neskorším zrušením | Pomenuje rozdiel, stav konania a jeho vplyv na oporu právneho tvrdenia. |
| Korpus nepokrýva relevantný dátum alebo pasáž | Uvedie konkrétnu medzeru a kde ju overiť. Citáciu pripojí iba k tomu, čo dodaná pasáž skutočne podporuje. |

Meraj zvlášť nájdené úseky, úseky vložené do otázky a platné citačné identifikátory. Pri právnom hodnotení skontroluj použiteľné znenie, správnosť výkladu, úplnosť, oporu jednotlivých tvrdení, chýbajúce tvrdenia a neodôvodnenú istotu. Slepé hodnotenie reálnych odpovedí odlíš od technických testov s fiktívnym adaptérom.
