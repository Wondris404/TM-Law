# Príprava špecializovaného modelu

Projekt trénuje adaptér nad používateľom dodaným lokálnym základom. `TM-Law-4B`, `TM-Law-6B` a `TM-Law-9B` sú ciele experimentov. V tomto vydaní sa vytvoril iba malý skúšobný adaptér pre umelý model. Overený právny tréningový korpus stále chýba.

## Dáta

Každý JSONL záznam potrebuje `id`, spoločnú `group` pre súvisiace prípady, `task`, `prompt`, `answer`, `provenance`, `license`, `origin`, `contains_personal_data: false` a `reusable_for_training: true`. K právnym materiálom pridajte `source_groups` pre rodiny znení a `source_ids` pre presnejšie odkazy. Rovnaké označenia rodín zachovajte v tréningových dátach aj v benchmarke. Pre lokálne identifikátory Slov-Lexu odvádza príprava rodinu predpisu aj z ID jeho časového znenia. Deklarácie o právach a anonymizácii musí skontrolovať človek.

```powershell
uv run --locked python -m scripts.prepare_training --input data/training-smoke.jsonl --holdout benchmarks/slovak-starter.jsonl --holdout benchmarks/slovak-family-law.jsonl --output .tm-law/train-smoke
```

Príprava vylúči zhodné normalizované otázky aj spoločné rodiny zdrojov s holdoutom. Odstráni identické duplicity, odmietne konfliktné dvojice a rozdelí nezávislé skupiny deterministicky na train, validation a test. Manifest obsahuje hashe vstupu, holdoutu aj každej časti. Preparafrázované otázky môžu prejsť kontrolou. Dopĺňajte preto spoločné skupiny aj manuálnu kontrolu.

## Voliteľná CPU skúška tréningu

Použite samostatné prostredie. GIT obsahuje iba syntetický vstup a skripty.

```powershell
uv venv .tm-law/train-env --python 3.12
uv pip install --python .tm-law/train-env/Scripts/python.exe --index https://download.pytorch.org/whl/cpu torch==2.10.0+cpu
uv pip install --python .tm-law/train-env/Scripts/python.exe -r training/requirements.txt
.\.tm-law\train-env\Scripts\python.exe -m scripts.make_training_smoke --data .tm-law/train-smoke --output .tm-law/smoke-base --run-directory .tm-law/smoke-run
.\.tm-law\train-env\Scripts\python.exe -m scripts.train_lora --config .tm-law/smoke-base/config.json
.\.tm-law\train-env\Scripts\python.exe -m scripts.train_lora --config .tm-law/smoke-base/config.json --resume-step 4
```

Na Linuxe je interpreter v `.tm-law/train-env/bin/python`. Skúška s osmi krokmi používa malý náhodne inicializovaný model a vlastný slovník. Je určená na kontrolu adaptéra, nie na odhad účinnosti právneho fine-tuningu. Výstup má `report.json`, `provenance.json`, adaptér a checkpointy. Overenie integrity a rovnakých parametrov je podmienkou obnovy. Používajte len vlastné checkpointy z rovnakého behu. Tréning nesťahuje váhy.

## LoRA alebo QLoRA nad skutočným základom

1. Vyberte model s podmienkami povoľujúcimi adaptáciu. Pri Qwen a RANA vyhodnoťte práva konkrétnych váh a revízie samostatne. Z verejného oficiálneho zdroja si podľa jeho návodu manuálne uložte revíziu modelu, konfiguráciu, tokenizer a súbory Safetensors.
2. Použite pripravené a právne overené dáta, pričom benchmark zostane mimo tréningu. Zadajte JSON podľa schémy [TrainingConfig](../training/config.py). Vyplňte `base_revision` úplným 40-znakovým SHA, `base_license`, cestu k lokálnemu základu, cieľové moduly a nový výstupný adresár. Pre transformer s lineárnymi `q_proj` a `v_proj` sú to kandidáti, cieľ overte v architektúre konkrétnej revízie.
3. Na ľahkú kontrolu vstupov použite `python -m scripts.train_lora --config miestna-konfiguracia.json --preflight`. Skontroluje miestne súbory základného modelu a tokenizéra, index a prítomnosť shardov, integritu splitov a vyhradené benchmarkové sady. Výstup uvádza veľkosti súborov na disku. Kontrola neotvára obsah váh, neimportuje PyTorch a nespúšťa tréning. RAM, kompatibilitu vrstiev a CUDA treba overiť oddelene na schválenom počítači.
4. Pre GPU prostredie použite oficiálny PyTorch pre CUDA. Voliteľná cesta `method: "qlora"` vyžaduje kompatibilnú NVIDIA CUDA a bitsandbytes. Nezahŕňa ju štandardná inštalácia. GPU a pamäť si overte pred spustením. `method: "lora"` umožňuje CPU pri vhodne malom základe. Pri Qwen 4B/9B treba tréningové nároky zmerať mimo cieľového notebooku.
5. Spustite `python -m scripts.train_lora --config miestna-konfiguracia.json`. Report eviduje hashe váh, seed, balíky, tréningovú stratu, testovaciu stratu pred a po a adaptér. Strata vyjadruje pravdepodobnosť správnych tokenov v dátach. Právnu použiteľnosť hodnotí oddelený benchmark a právnik.

Ak už máte kompatibilný lokálny GGUF výsledného modelu, vytvorte vedľa neho `Modelfile` s jediným riadkom `FROM ./tm-law-4b.gguf` a spustite `ollama create tm-law-4b:experimental -f Modelfile`. Pred importom skontrolujte architektúru, modelovú šablónu a licenciu. Kompatibilita konkrétneho adaptéra závisí od základu a formátu a nebola overená pre cieľové Qwen modely. [Import do Ollamy](https://docs.ollama.com/import)

## Kompresia a zachovanie schopností

Porovnajte základ, adaptovanú variantu a jednotlivé kvantizácie s identickým held-out korpusom a konfiguráciou. Aplikácia pri zvolenom lokálnom modeli použije rovnaké vyhľadávanie. `scripts.compare_model_runs` porovná zhodné úlohy a konfigurácie a vypíše dostupné rozdiely latencie, rýchlosti a pamäte. Odborné posudky spracujte osobitne cez `scripts.legal_review`.

```powershell
uv run --locked python -m scripts.compare_model_runs --baseline .tm-law/base.json --candidate .tm-law/variant.json --output .tm-law/comparison.json
```

Prvý návrh kompresie je porovnať menší študentský model a viac kvantizácií na rovnakom CPU. Pri odstránení multimodálnych váh overte kompatibilitu textového formátu a skutočnú rezidentnú pamäť. Pri pruningu alebo destilácii sledujte aj zachovanie slovenčiny, češtiny, logiky a práce s dôkazmi. Cielené unlearning experimenty robte na kópii a oddeľte zabudnutie od zachovania schopností. Zmena správania sama nezmenšuje počet parametrov ani pamäť. Tieto experimenty zatiaľ nemajú merania na cieľových modeloch. [Výskumný plán](RESEARCH.md)
