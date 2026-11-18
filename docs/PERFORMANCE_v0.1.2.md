# Overenie výkonu a tréningu

Merania vznikli 18. novembra 2026 v Linuxe x86_64 s kvótou štyroch jadier a bez CUDA. Použil som skutočnú Ollamu 0.40.16 a malý náhodne inicializovaný lokálny model architektúry Llama s približne 1,38 milióna parametrov. Ollama počúvala iba na loopbacku, cloud bol vypnutý, požiadavky boli postupné a použilo sa `num_gpu=0`.

| Formát | Kontext | Dokončené | Načítanie s | Prvý token s | Latencia s | Tok/s | Backend RSS MiB | Max. RSS procesu Ollamy MiB | Spoločné PSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F16 | 2048 | 2/2 | 0.284 | 0.682 | 1.186 | 137.90 | 40.98 | 36.32 | 102.64 |
| F16 | 4096 | 2/2 | 0.279 | 0.538 | 0.996 | 139.74 | 43.08 | 36.52 | 107.12 |
| F16 | 8192 | 2/2 | 0.274 | 0.489 | 0.835 | 193.49 | 43.11 | 39.82 | 116.33 |
| Q4_K_M | 2048 | 2/2 | 0.258 | 0.478 | 0.808 | 186.31 | 44.52 | 36.65 | 106.43 |
| Q4_K_M | 4096 | 2/2 | 0.263 | 0.522 | 0.943 | 151.43 | 44.53 | 36.65 | 108.22 |
| Q4_K_M | 8192 | 2/2 | 0.257 | 0.492 | 0.818 | 190.18 | 45.24 | 39.27 | 117.90 |

Časy a rýchlosť v tabuľke sú mediány z dvoch opakovaní na konfiguráciu. RSS je najvyššia pozorovaná hodnota jedného procesu počas behu. Spoločná špička PSS pochádza zo simultánnej snímky backendu a detegovaných procesov Ollamy. Všetkých 12 odpovedí dosiahlo limit 64 tokenov. V tomto prípade je to očakávaný výsledok testu prenosu a výkonu. Režim bol Auto, pretože model nepodporuje samostatné uvažovanie.

Veľkosť modelového záznamu podľa Ollamy klesla z 2,768,209 na 857,428 bajtov; spoločná fyzická pamäť neklesla v týchto pozorovaniach. Dva behy na konfiguráciu stačia na kontrolu merania. Nezakladajú všeobecný záver o voľbe kvantizácie. Testovací model nemá právnu ani jazykovú kvalitu relevantnú pre nasadenie. Výkon Qwen 4B, 9B a RANA 9B na Lenovo a limit 12 GB zatiaľ nemajú meranie.

Na prípravu reprodukovateľného testu použite `scripts.make_inference_smoke` v tréningovom prostredí s doinštalovaným `sentencepiece`. Vytvorte F16 GGUF pomocou oficiálneho `convert_hf_to_gguf.py` z revízie llama.cpp `bafa0420c1e57edf04d71587d32fe57d45df7b95`. Vytvorte Q4 variant pomocou `llama-quantize VSTUP.gguf VYSTUP.gguf Q4_K_M` z vydania `b12359`. Každý GGUF sa importuje cez svoj `Modelfile` s `FROM ./model.gguf`. Ollama 0.40.16 vyžaduje pri GGUF kvantizáciu pred importom. Reálne modely sa pripravujú samostatne podľa [návodu pre Windows](WINDOWS_SETUP.md).

CPU skúška LoRA použila iný umelý textový model s 69,504 parametrami, z ktorých bolo 768 trénovateľných. Sada mala 8 tréningových, 1 validačný a 1 testovací príklad. Prebehlo 8 krokov so seedom 42. Testovacia strata bola 4.639444 pred a 4.639284 po tréningu. Obnovenie z kroku 4 vytvorilo bajtovo rovnaké váhy adaptéra. Jeden syntetický testovací príklad neposkytuje dôkaz o zlepšení schopností. Vytrénované váhy nie sú v Gite.

V tomto behu bolo importovaných 0 autentických právnych dokumentov a 0 autentických znení. Právna štartovacia sada obsahuje 13 syntetických scenárov, z toho 0 hodnotených právnikom. Podrobné strojovo čitateľné údaje sú v [súbore meraní](evidence/v0.1.2-smoke.json).
