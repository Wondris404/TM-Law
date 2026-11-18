# Pokrytie právnych zdrojov

Pri pôvodnom cloudovom overení žiadny z testovaných právnych portálov nesprístupnil obsah pre strojové overenie. Slov‑Lex, NR SR a EUR‑Lex výslovne vracali HTTP 403. Pri neskoršom overení oficiálne tlačové exporty Slov-Lex poskytli dve autentické časové znenia zákona o rodine. Projekt ich importuje offline podľa [pokrytia korpusu](LEGAL_CORPUS_STATUS.md). Balík v `data/corpus-example` je výslovne fiktívny a slúži na test importu. Citačné karty ho označujú a pri reálnej inferencii je vylúčený.

| Zdroj | Legitímna cesta pre lokálny import | Stav v tomto behu |
| --- | --- | --- |
| [Slov‑Lex](https://www.slov-lex.sk/) | Na stránke predpisu vybrať konkrétne časové znenie. Uložiť verejný export alebo HTML/PDF, zaznamenať URL znenia a dátum účinnosti z oficiálnych údajov. | Dva oficiálne tlačové exporty zákona o rodine a ich PDF boli dostupné. Zvyšné predpisy čakajú na overenie. |
| [Národná rada SR](https://www.nrsr.sk/) | Stiahnuť zverejnený dokument Ústavy, ak prístup aj licenčné podmienky dovoľujú. Rozhodujúce znenie doložiť samostatne. | Kontrola verejnej ústavnej stránky vrátila 403. |
| [Najvyšší súd SR](https://www.nsud.sk/), [Najvyšší správny súd SR](https://www.nssud.sk/) a [Ústavný súd SR](https://www.ustavnysud.sk/) | Použiť verejne zverejnené a podľa potreby anonymizované PDF rozhodnutia. Zaznamenať súd a spisovú značku z originálu. | Dokumenty a podmienky hromadného prístupu sa nepodarilo overiť. |
| [Ministerstvo spravodlivosti SR](https://www.justice.gov.sk/) | Použiť zverejnené rozhodnutie z oficiálneho vyhľadávania. Nezamieňať publikáciu s oprávnením na hromadné ďalšie použitie. | Nedostupné na overenie v cloude. |
| [EUR‑Lex](https://eur-lex.europa.eu/) | Vybrať slovenské jazykové znenie a jeho konkrétnu verziu. Rozlišovať pôvodný akt a konsolidované znenie a skontrolovať pravidlá opakovaného použitia. | Verejná stránka vrátila 403. |
| [HUDOC](https://hudoc.echr.coe.int/) | Uložiť verejný text rozhodnutia alebo oficiálny textový PDF s identifikátorom dokumentu. Preklad a originál evidovať osobitne. | Nedostupné na overenie v cloude. |

V korpuse chýbajú predpisy **460/1992, 162/2015, 40/1964, 160/2015, 161/2015, 300/2005, 301/2005, 513/1991 a 311/2001**, ďalšie znenia **36/2005** a judikatúra. Pred zaradením prvého dokumentu skontrolujte pôvodný zdroj, podmienky jeho použitia, dátum vyhlásenia, účinnosť a prípadné prechodné ustanovenia. Manuálny import necertifikuje povolenie na ďalšie šírenie ani pôvod údajov, ktoré používateľ vložil. [Import a integrita](LEGAL_DATA.md)
