# Východisková diagnostika TM-Law

Audit začal 18. novembra 2026 v izolovanom linuxovom klone. Východisková verzia bola 0.1.2 na čistom `main`. Lokálny HEAD a `origin/main` zhodne ukazovali na `55f3157440fdf3cbe2a773d806f6eef873641dca`. Repozitár nemal tag vydania. Cieľový Windows klon, necommitnuté zmeny používateľa a hardvér Lenovo neboli z tohto prostredia dostupné.

## História a zistenia

| Revízia | Overený obsah | Chýbajúci dôkaz |
| --- | --- | --- |
| `9b26ceb` a `6556aea` | SQLite/FTS5, FastAPI, React, lokálny chat a CI | Právna kvalita odpovedí |
| `98aaa50` | PowerShell spúšťač a overenie režimu Mock | Spustenie na cieľovom Lenovo |
| `5bc014a` | Archív originálov, SHA-256, index a intervaly účinnosti | Autentické zdroje vo východiskovej databáze |
| `d0667b6` | 13 syntetických úloh, zaslepené hodnotenie | Odborné posudky a zdrojovo podložené úlohy |
| `3275622` a `50c5105` | Príprava datasetov, tréningový skript a merania syntetických modelov | Inferencia a špecializácia Qwen |
| `55f3157` | Kontrola archivovanej referencie a jej účinnosti pred inferenciou | Validácia reálneho korpusu a modelu naraz |

RAG kontroluje iba to, či identifikátor citácie patrí do kontextu modelu. Lexikálne vyhľadávanie podporuje priame číslo predpisu, paragraf a dátum. Dátumový výber používa zahrnutý začiatok a vylúčený koniec. Časovú pôsobnosť z prechodných ustanovení musí právnik posúdiť osobitne. Priamy JSON import ponecháva zdroje bez archivovaného originálu. Režim právneho auditu pri chýbajúcej databáze pôvodne skončil chybou SQLite. Pred auditom treba najprv vytvoriť a naplniť databázu.

Súkromné dokumenty sa extrahujú v podprocese s časovým limitom. Samotný podproces nevynucuje izoláciu OS ani spoľahlivý pamäťový strop. Text dokumentov a história prehliadača nemajú aplikačné šifrovanie. Podrobnosti sú v [bezpečnostnej dokumentácii](SECURITY.md).

## Overenia na východiskovej revízii

| Kontrola | Výsledok |
| --- | --- |
| `pytest -q -rA`, Linux, CPython 3.12.16 | 45 úspešných, 0 zlyhaných, 1 preskočený pre chýbajúci lokálny model Ollama |
| Ruff lint a format | Prešli, 32 súborov zodpovedalo formátu |
| TypeScript a produkčný build | Prešli s Node 22.23.5, frontend 0.1.2 |
| Benchmarkový smoke | 13/13 dokončených simulácií |
| Príprava tréningových dát | 8 train, 1 validation, 1 test, všetky syntetické |
| Korpusový smoke | 1 syntetický archív, 2 pasáže, 0 autentických zdrojov |
| Vzdialené CI | Úspešné Linux a Windows kontroly vrátane spúšťača Mock na Windows runneri. [Výsledok](https://github.com/Wondris404/TM-Law/actions/runs/44386380792) |
| Prehliadač na cloudovom hostiteľovi | Chromium sa nespustilo pre chýbajúce systémové knižnice. Bez inštalácie systémových balíkov. |

Po zavedení úsporného režimu sa lokálne spúšťajú iba cielené ľahké kontroly. Štandardné overenie zmien zabezpečuje existujúce GitHub Actions.

| Míľnik | Stav pri začiatku | Zvyšná práca |
| --- | --- | --- |
| v0.1.2 | Partial | Ollama a merania Qwen na cieľovom Windows |
| v0.2 | Partial | Import autentických časových znení a rozhodnutí |
| v0.3 | Partial | Právne podložené úlohy, nezávislé hodnotenie a porovnanie modelov |
| v0.4 | Partial | Adaptácia skutočného modelu, porovnanie kompresie a kvality |
