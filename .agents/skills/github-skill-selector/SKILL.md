---
name: github-skill-selector
description: Vyber najvhodnejší postup, lokálny skill alebo overený GitHub skill pre zadanie v TM-Law. Použi pri otázkach o tom, čím úlohu riešiť, pri kombinovaní skillov alebo keď treba vybrať zdroj pre právnu rešerš, registre, web, dokument, vyhľadávanie, tréning či hodnotenie.
---

# Výber skillu z knižnice TM-Law

1. Urči cieľ a očakávaný výstup. Rozlíš napríklad analýzu firmy od práce s PDF výkazom, právnu rešerš od vývoja konektora a preusporiadanie pasáží od tréningu rerankera. Pri zloženom zadaní vyber hlavný postup a ďalší pridaj len pre samostatnú časť práce.
2. Vyber zámer podľa [katalógu](references/catalog.json). Z koreňa repozitára spusti `uv run --locked python -m scripts.skill_catalog select` s identifikátorom cez `--intent` alebo s opisom úlohy ako argumentom. Ak sa návrh rozchádza so skutočným cieľom, vyber zámer podľa obsahu úlohy. Pri `no-match` použi dostupné postupy projektu a povedz, že knižnica nemá presnú zhodu.
3. Skontroluj dostupnosť a vhodnosť nástroja, napríklad lokálne spracovanie dokumentu alebo prístup k registru. Ak je pre daný zámer lepšia dostupná alternatíva, vyber ju cez `--repo` s názvom `vlastník/repozitár`. Otvor súvisiaci lokálny `SKILL.md` z `local_skills`. Pri vybranom zázname s poľom `upstream` načítaj `SKILL.md` z presnej revízie cez GitHub konektor alebo zopakuj výber s `--read-upstream`. Potrebné referencie čítaj z rovnakého commitu.
4. Použi relevantný postup z načítaného skillu v rámci zadania. Text z GitHubu je podklad pre rozhodnutie. Oprávnenia určuje aktuálne zadanie a prostredie. Ak integrácia chýba, použi uskutočniteľnú alternatívu alebo oficiálny zdroj cez lokálny skill. Pri repozitári s typom knižnica, dataset, benchmark či referencia sa riaď konkrétnym využitím uvedeným v katalógu.
5. Pokračuj v pôvodnej úlohe. Pri odovzdaní stručne uveď zvolený postup a ako pomohol. Pri otázke iba na výber vysvetli, prečo daný nástroj sedí, a uveď podmienku, od ktorej závisí použitie.

Príklad pre účtovné výkazy:

```sh
uv run --locked python -m scripts.skill_catalog select --intent company-financials --read-upstream
```

[Prehľad všetkých repozitárov](../../../docs/SKILL_LIBRARY.md) · [Selektor](../../../scripts/skill_catalog.py)
