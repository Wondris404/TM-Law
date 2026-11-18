# Benchmarky

```sh
uv run --locked python -m scripts.benchmark
```

Predvolený beh vytvorí dočasnú SQLite databázu, importuje fiktívne znenia a spustí tri scenáre s testovacím adaptérom. Históriu overuje porovnaním očakávaných ID s citovanými ID a eviduje aj to, či úloha bez dostupného znenia nenahlásila zdroj. Výstup označuje simuláciu. Ani jej úspešný výsledok nehodnotí právnu správnosť a čas nepredstavuje latenciu modelu.

Pre porovnanie reálnych modelov použite vlastný odborne overený JSONL súbor rovnakej štruktúry a lokálny korpus. Voliteľné polia sú `query`, `as_of`, `reference_answer`, `criteria` a `fictional`. Úlohy označené ako fiktívne sa pri reálnom modeli vynechajú. Príklad:

```sh
uv run --locked python -m scripts.benchmark --cases overene.jsonl --data-dir .tm-law --model qwen3.5:4b --model qwen3.5:9b
```

Výstup eviduje dokončené a chybové behy, platnosť identifikátorov (podiel jedinečných), záchyt očakávaných zdrojov, zhodu identifikátorov pri historických úlohách a latenciu. Tokeny za sekundu vypočíta z metadát Ollamy, ak ich runtime poskytne. Špičková RAM, veľkosť modelu a miera neopodstatnených odmietnutí sú zatiaľ `null`. Na ich vyhodnotenie treba meranie celého procesu Ollama, údaje o konkrétnych váhach a ľudské anotácie. Kategórie zapisujte do poľa `category`. Používateľské benchmarkové súbory a výstup môžu obsahovať citlivé údaje.
