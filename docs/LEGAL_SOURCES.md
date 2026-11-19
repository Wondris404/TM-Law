# Pokrytie právnych zdrojov

Pri pôvodnom cloudovom overení vracali Slov‑Lex, NR SR a EUR‑Lex HTTP 403. Neskôr poskytol verejný tlačový export Slov-Lex šesť časových znení troch slovenských predpisov. Pri reálnej inferencii sa výslovne fiktívny balík `data/corpus-example` vylučuje. [Pokrytie a offline import](LEGAL_CORPUS_STATUS.md)

| Zdroj | Legitímna cesta pre lokálny import | Stav v tomto behu |
| --- | --- | --- |
| [Slov‑Lex](https://www.slov-lex.sk/) | Na stránke predpisu vybrať konkrétne časové znenie. Uložiť verejný export alebo HTML/PDF, zaznamenať URL znenia a dátum účinnosti z oficiálnych údajov. | Tlačové HTML a PDF pre tri znenia zákona o rodine, dve znenia ústavy a jedno znenie správneho poriadku poskytol `static.slov-lex.sk` so stavom 200. |
| [Národná rada SR](https://www.nrsr.sk/) | Stiahnuť zverejnený dokument Ústavy, ak prístup aj licenčné podmienky dovoľujú. Rozhodujúce znenie doložiť samostatne. | Predchádzajúca kontrola verejnej ústavnej stránky vrátila 403. Tento krok ju neopakoval. Znenie 460/1992 v korpuse je z tlačového exportu Slov-Lex. |
| [Najvyšší súd SR](https://www.nsud.sk/), [Najvyšší správny súd SR](https://www.nssud.sk/) a [Ústavný súd SR](https://www.ustavnysud.sk/) | Použiť verejne zverejnené a podľa potreby anonymizované PDF rozhodnutia. Zaznamenať súd a spisovú značku z originálu. | Dokumenty a podmienky hromadného prístupu sa nepodarilo overiť. |
| [Ministerstvo spravodlivosti SR](https://www.justice.gov.sk/) | Použiť zverejnené rozhodnutie z oficiálneho vyhľadávania. Nezamieňať publikáciu s oprávnením na hromadné ďalšie použitie. | Nedostupné na overenie v cloude. |
| [EUR‑Lex](https://eur-lex.europa.eu/) | Vybrať slovenské jazykové znenie a jeho konkrétnu verziu. Rozlišovať pôvodný akt a konsolidované znenie a skontrolovať pravidlá opakovaného použitia. | Verejná stránka vrátila 403. |
| [HUDOC](https://hudoc.echr.coe.int/) | Uložiť verejný text rozhodnutia alebo oficiálny textový PDF s identifikátorom dokumentu. Preklad a originál evidovať osobitne. | Nedostupné na overenie v cloude. |

V korpuse chýbajú predpisy **162/2015, 40/1964, 160/2015, 161/2015, 300/2005, 301/2005, 513/1991 a 311/2001**, ďalšie znenia už načítaných predpisov a judikatúra. Pred zaradením dokumentu skontrolujte pôvodný zdroj, podmienky jeho použitia, dátum vyhlásenia, účinnosť a prípadné prechodné ustanovenia. [Import a integrita](LEGAL_DATA.md)
