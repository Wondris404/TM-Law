# TM-Law v0.1.1 · Thomas More Legal AI

Lokálny právny asistent pre slovenských advokátov. MVP prepája právne vyhľadávanie v SQLite, porovnávanie dátumov účinnosti, streamovaný chat s lokálnou Ollamou a kontrolu citačných identifikátorov. Súkromné dokumenty spracúva na počítači používateľa.

## Spustenie

Predpoklady sú Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 24 s npm a pre skutočnú inferenciu [Ollama](https://ollama.com/download). Postup pre Windows vrátane spúšťača, prípravy modelu a offline skúšky je v [WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md).

Z koreňa repozitára:

```sh
uv sync --locked
npm --prefix frontend ci
npm --prefix frontend run build
uv run --locked python -m uvicorn backend.tm_law.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Otvorte `http://127.0.0.1:8000`. Vytvorí sa prázdna databáza v `.tm-law/`. Pridajte export s overeným pôvodom cez **Právna databáza → Importovať znenie predpisu alebo rozhodnutie** alebo cez `uv run --locked python -m scripts.import_legal VAS_SUBOR.json`. Formát a význam dátumov popisuje [LEGAL_DATA.md](docs/LEGAL_DATA.md).

## Ukážkový režim

Ukážková databáza obsahuje dva výslovne fiktívne predpisy. Použite samostatný dátový adresár, aby sa ukážky nemiešali s pracovnými údajmi. V POSIX shelli:

```sh
uv run --locked python -m scripts.import_legal data/demo-2022.json --data-dir .tm-law/demo
uv run --locked python -m scripts.import_legal data/demo-2024.json --data-dir .tm-law/demo
TM_LAW_ADAPTER=mock TM_LAW_DATA_DIR=.tm-law/demo uv run --locked python -m uvicorn backend.tm_law.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

V databáze vyhľadajte `9999/2099 § 7 evidencia` k dátumu `2022-12-20` a potom k `2024-01-01`. V chate položte otázku o evidencii dielne a zadajte rozhodujúci dátum. Testovací adaptér poskytne označenú simuláciu s odkazom na nájdený úsek.

## Vývoj

Po spustení backendu na porte 8000 použite `npm --prefix frontend run dev` pre rozhranie s automatickým načítaním zmien. Vite posiela požiadavky `/api` lokálnemu backendu.

```sh
uv run --locked ruff check backend scripts tests
uv run --locked ruff format --check backend scripts tests
uv run --locked pytest -q
uv run --locked python -m scripts.benchmark
npm --prefix frontend run build
```

V nastaveniach môžete zvoliť režim uvažovania Ollamy a voliteľne merať pamäť procesov. Porovnanie modelov, kontextov alebo režimov sa spúšťa cez [benchmark](docs/BENCHMARKS.md).

MVP podporuje TXT, PDF s textovou vrstvou a DOCX. Históriu si prehliadač pamätá lokálne, pričom každá otázka sa posudzuje samostatne. Dôverné údaje a odpovede sa ukladajú bez aplikačného šifrovania. Zdrojová karta overuje identitu použitého úseku, právnu použiteľnosť a úplnosť zdrojov musí posúdiť právnik.

[Architektúra](docs/ARCHITECTURE.md) · [Modely](docs/MODELS.md) · [Bezpečnosť](docs/SECURITY.md) · [Benchmarky](docs/BENCHMARKS.md) · [Výskum](docs/RESEARCH.md) · [Ďalšie kroky](docs/ROADMAP.md) · [Poznámky k v0.1.1](docs/RELEASE_0.1.1.md)
