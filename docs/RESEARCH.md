# Výskum menšieho slovenského právneho modelu

Najprv zmerajte pôvodný Qwen (A) a RANA (B) pri rovnakých dátach, kontexte, kvantizácii a nastaveniach. Metriky rozdeľte na právne hodnotenie ľuďmi, integritu citácií, vyhľadávanie a výkon na cieľovom CPU. Pred anotáciou referenčných odpovedí uložte presné znenia a dátumy. Publikované postupy sú zdrojmi hypotéz. Priame výsledky pre slovenské právo v tomto projekte zatiaľ chýbajú.

| Experiment | Návrh a podmienka pokračovania |
| --- | --- |
| Domain-adaptive pretraining | Skúšať až po zdokumentovaní korpusu a práv na opätovné použitie. Udržať časový alebo dokumentový odstup testov a porovnať s nezmeneným modelom. [Gururangan et al.](https://aclanthology.org/2020.acl-main.740/) |
| Supervised legal fine-tuning | Model C trénovať na odborne posúdených odpovediach s dôkazmi, neistotou a platným formátom citácií. Manuálne hodnotenie vykonať zaslepene. |
| LoRA a QLoRA | Skúsiť oddelené adaptéry pred zásahmi do základných váh. Tréningové požiadavky merať osobitne od CPU inferencie. [LoRA](https://arxiv.org/abs/2106.09685), [QLoRA](https://arxiv.org/abs/2305.14314) |
| Kvantizácia | Pri rovnakých otázkach zmerať celkovú RAM, latenciu a stratu presnosti podľa zvolenej kvantizácie, dĺžky kontextu a runtime. [GGUF](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) |
| Structured pruning | Pokus robiť na kópii a porovnať reálny čas na CPU. Menší počet nominálnych parametrov sám osebe neurčuje rýchlosť. [LLM-Pruner](https://arxiv.org/abs/2305.11627) |
| Knowledge distillation | Model E použiť až po výbere licenčne použiteľného učiteľa. Odborný audit musí vyhodnotiť aj chyby prenesené z učiteľa. [Hinton et al.](https://arxiv.org/abs/1503.02531) |
| Targeted machine unlearning | Model D pripraviť iba po referenčnom meraní a s vratným experimentom na kópii. Oddelene merať cielené zabudnutie a zachovanie schopností. [TOFU](https://arxiv.org/abs/2401.06121) |
| Text-only architektúra | Na rovnakom CPU porovnať model nasadzovaný bez multimodálnych komponentov. Potvrdiť, či rozdiel vo veľkosti artefaktov znamená rozdiel v rezidentnej pamäti. |
| Slovenská evaluácia | Zahrnúť skloňovanie, jazyk judikatúry, kontext EÚ, konflikty znení a právne prípustné citlivé otázky. Referencie musia obsahovať číslo, dátum a úsek. |
| Zachovanie znalostí | Každú úpravu porovnať na udržiavacej sade (jazyk, všeobecné uvažovanie, zdroje, čítanie dokumentov) a merať zmeny oproti referencii. [Continual Learning in Neural Networks](https://arxiv.org/abs/1802.07569) |

V tomto MVP sa modelové váhy nemenia. Benchmark runner slúži ako rozhranie pre porovnanie lokálnych modelov po zostavení overenej sady.
