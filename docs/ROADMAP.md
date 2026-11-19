# Najbližšie míľniky

| Míľnik | Stav | Čo bráni dokončeniu |
| --- | --- | --- |
| v0.1.2 | Čiastočne | Meranie Ollamy a Qwen na cieľovom notebooku. Inferencia sa v úspornom režime nespúšťa. |
| v0.2 | Čiastočne | V korpuse sú tri overené predpisy. Osem prioritných kódexov a judikatúra čakajú na povolený oficiálny export. Text sa nedopĺňa. |
| v0.3 | Čiastočne | Deterministické kontroly a označené syntetické úlohy existujú. Sada 200 otázok a posudok právnika nie sú hotové. `expert_verified` zostáva vypnuté. |
| v0.4 | Pripravené len ako kód | LoRA/QLoRA, holdout a destilácia sú v skriptoch. Váhy sa nesťahujú a tréning sa nespúšťa. |

Hotové v úspornom režime: archivovaný import, SHA-256, historické intervaly, varovanie na chýbajúce prioritné predpisy, prekrytie účinnosti, opakovanie textu úseku, povinná identita rozhodnutia, citácie vrátane písmen, nepodložené označenia a odstránenie značiek z textu, ktorý ide do modelu.

Infraštruktúra pokrýva import s archivovaným originálom, slovenskú štartovaciu sadu a prípravu LoRA/QLoRA. Skutočné pokrytie verejného práva a odborné overenie sú samostatné míľniky. [Pokrytie](LEGAL_SOURCES.md) · [Tréning](TRAINING.md)
