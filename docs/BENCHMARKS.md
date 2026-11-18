# Benchmarky v0.1.1

## Lokálna simulácia

```powershell
New-Item -ItemType Directory -Force .tm-law | Out-Null
uv run --locked python -m scripts.benchmark --summary --output .tm-law/mock-benchmark.json
```

Pri použití `--output` musí nadradený adresár existovať. Bez tohto parametra ide UTF‑8 JSON na štandardný výstup. Pre Windows PowerShell 5.1 použite `--output` pri ukladaní do súboru, pretože presmerovanie konzoly môže zmeniť kódovanie. `--summary` vypíše tabuľku na štandardný chybový výstup. Predvolený beh použije dočasnú databázu, fiktívne znenia a tri scenáre s testovacím adaptérom. Čas simulácie necharakterizuje výkon modelu.

## Reálne modely

Bez `--cases` sa pri zadaní `--model` spustí krátka diagnostická otázka bez očakávanej právnej citácie. Hodí sa na meranie času a komunikácie, právnu kvalitu neposudzuje. Na laptop najprv spustite iba 4B model s kontextom 2 048:

```powershell
New-Item -ItemType Directory -Force .tm-law | Out-Null
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --context-window 2048 --reasoning off --reasoning on --repeats 2 --measure-memory --summary --output .tm-law/qwen-4b-2048.json
```

Po stabilnom behu porovnajte ďalšie lokálne nainštalované tagy a kontexty. Jeden proces benchmarku posiela požiadavky postupne a každá žiada Ollamu o uvoľnenie modelu po odpovedi (`keep_alive=0`). Zatvorte paralelné chaty. Spustite Ollamu s `OLLAMA_MAX_LOADED_MODELS=1` a `OLLAMA_NUM_PARALLEL=1`. Najvyšší kontext 8 192 skúšajte až po kontrole rezervy pamäte.

```powershell
uv run --locked python -m scripts.benchmark --model qwen3.5:4b --model qwen3.5:9b --model abliterant/qwen3.5-rana:9b --context-window 4096 --reasoning auto --summary --output .tm-law/modely.json
```

Pre právne porovnanie pridajte `--cases overene.jsonl --data-dir .tm-law/praca`. Formát úloh vychádza z [ukážkového JSONL](../benchmarks/smoke.jsonl). Vyžadované sú `id`, `category`, `question` a `expected_sources`. Pri hodnotení historického znenia použite kategóriu `historické znenia` a presný `as_of`. Zadajte `expert_verified` iba pri odborne overenej referencii. Fiktívne úlohy sa pri reálnej inferencii vylúčia. Pred porovnaním nástroj urobí jednu snímku právnej databázy bez databázy súkromných dokumentov. Zapíše hash korpusu a vstupných úloh, modelový digest podľa Ollamy a parametre, vrátane `--seed`, `--temperature` a `--max-tokens`. Rovnaký seed nezaručuje identický výstup na rôznom hardvéri.

Výstup obsahuje stav, dĺžkový limit, latenciu, čas k prvému tokenu a k prvému viditeľnému tokenu, počet tokenov a rýchlosť podľa runtime. Pri zapnutom uvažovaní počet generovaných tokenov môže zahŕňať aj interné tokeny. Validita citačných identifikátorov, záchyt zdrojov a zhoda historických ID hodnotia identifikátory. Polia pre odborné posúdenie právnej správnosti a úplnosti sú prázdne, kým ich nevyplní hodnotiteľ. Príznak ukončenia generovania sám neurčuje odbornú úplnosť.

Predvolený report neobsahuje otázky ani odpovede. Text odpovedí pripojí len `--include-answers`. Aj identifikátory a názvy benchmarkových úloh môžu byť citlivé. Na meranie používajte verejné alebo výslovne schválené testovacie údaje a reporty ukladajte mimo Gitu.

## Interpretácia pamäte

| Metrika | Význam |
| --- | --- |
| Špičkové RSS procesu | Najvyššia pozorovaná rezidentná pamäť medzi snímkami. Na Windows ide o working set. Môže zahŕňať zdieľané stránky. |
| Špičkové USS procesu | Pozorovaná pamäť jedinečná pre proces, ak ju OS sprístupní. Nezahŕňa zdieľanú časť. |
| Spoločná špička PSS | Súčet pomerných podielov zdieľaných stránok z jednej snímky, keď sa podarí priradiť lokálny Ollama listener aj procesy potomkov a OS sprístupní PSS. Na Windows sa zvyčajne nevykazuje. |
| Pamäť celého systému | Pozorované `total - available` z psutil. Zahŕňa aj procesy mimo TM‑Law a Ollamy. |

Snímky sa zbierajú každých 0,5 sekundy počas voliteľného merania. Krátke špičky medzi snímkami môžu uniknúť. RSS nesčítavame. Virtuálna pamäť je adresný priestor a veľkosť súboru váh je disková metrika. Ani jedna nevyjadruje spotrebu fyzickej RAM. Prehliadač, iné procesy, nepriradené WSL procesy a zdieľaná pamäť iGPU môžu zostať mimo odhadu. Pri neznámom celku nemožno potvrdiť limit 12 GB iba z RSS.

| Model | Uvažovanie | RAM | Tok/s | Latencia |
| --- | --- | --- | --- | --- |
| Qwen3.5 4B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |
| Qwen3.5 9B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |
| Qwen3.5 RANA 9B | off / on, podľa podpory | Zmerať na Lenovo | Zmerať | Zmerať |
