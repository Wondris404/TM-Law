# Knižnica GitHub zdrojov pre TM-Law

Katalóg obsahuje **30 repozitárov** a **6 pripnutých GitHub skillov**.
Typ pri položke označuje jej využitie v TM-Law. Odkaz v stĺpci Skill vedie na konkrétny commit pôvodného návodu.

V Codexe použi [$github-skill-selector](../.agents/skills/github-skill-selector/SKILL.md). Strojový zoznam a mapovanie úloh sú v [catalog.json](../.agents/skills/github-skill-selector/references/catalog.json).

## Webová rešerš

| Repozitár | Typ | Použitie v TM-Law | Skill |
| --- | --- | --- | --- |
| [ItzCrazyKns/Vane](https://github.com/ItzCrazyKns/Vane) | referencia | Režimy webovej rešerše, Ollama a citácie v používateľskom rozhraní. | — |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | aplikácia | Plánovanie podtém, paralelné čítanie a syntéza reportu v Pythone. | [gpt-researcher](https://github.com/assafelovic/gpt-researcher/blob/ddd4db36208d9c8e49f3b2436efda97baecb5433/skills/gpt-researcher/SKILL.md) |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) | referencia | Krátka iteračná slučka s doplňujúcimi dopytmi podľa zistení. | — |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | referencia | Konfigurovateľné zdroje, MCP a limit iterácií. GitHub eviduje repozitár ako archivovaný. | — |
| [searxng/searxng](https://github.com/searxng/searxng) | služba | Vlastná inštancia metavyhľadávača pre ďalší zdroj výsledkov vedľa Brave. | — |
| [adbar/trafilatura](https://github.com/adbar/trafilatura) | knižnica | Extrakcia hlavného textu, dátumu a tabuliek z HTML v Pythone. | — |

## Slovenské právo, firmy a verejné registre

| Repozitár | Typ | Použitie v TM-Law | Skill |
| --- | --- | --- | --- |
| [originalmagneto/RUZ-MCP](https://github.com/originalmagneto/RUZ-MCP) | konektor | Z IČO k závierkam, výkazom, šablónam a PDF. Tržby a výsledok hospodárenia overuj v konkrétnom výkaze. | [ruz-uctovne-zavierky](https://github.com/originalmagneto/RUZ-MCP/blob/c2dd4a07565c7d30bc5ebcc28f35a7cec36421f5/skills/ruz-uctovne-zavierky/SKILL.md) |
| [ESKRiPO/Slov-Lex_MCP](https://github.com/ESKRiPO/Slov-Lex_MCP) | konektor | Stránkované načítanie predpisu podľa dátumu účinnosti. Vzor pre import časových znení. | — |
| [legalize-dev/legalize-sk](https://github.com/legalize-dev/legalize-sk) | dataset | Porovnanie slovenských predpisov v Gite. Verzie bez dátumu účinnosti alebo dostupného textu projekt preskakuje. | — |
| [LawCodex/sk](https://github.com/LawCodex/sk) | dataset | Snímka konsolidovaných textov a mapovanie identifikátorov na zdroj Slov-Lexu. | — |
| [ShepDogSk/rpo-mcp-server](https://github.com/ShepDogSk/rpo-mcp-server) | konektor | Vyhľadanie podľa názvu alebo IČO, detail subjektu a jeho história v RPO. | — |
| [byrokrat-sk/register-parser](https://github.com/byrokrat-sk/register-parser) | knižnica | Štruktúrovaná extrakcia z ORSR, živnostenského registra a ďalších portálov. | — |
| [otvorenesudy/otvorenesudy](https://github.com/otvorenesudy/otvorenesudy) | aplikácia | Vzor vyhľadávania a dátového modelu slovenských súdnych rozhodnutí. | — |
| [vargadavid304/slovak-court-decisions-dataset](https://github.com/vargadavid304/slovak-court-decisions-dataset) | dataset | Anotované odkazy z rozhodnutí na predpisy a judikatúru. Pred použitím datasetu over podmienky jeho použitia. | — |
| [zltastopa/zmluvy](https://github.com/zltastopa/zmluvy) | aplikácia | Vzor vyhľadávania zmlúv v CRZ podľa IČO, protistrany a textu. | — |

## Právo EÚ, ekonomika a konektory

| Repozitár | Typ | Použitie v TM-Law | Skill |
| --- | --- | --- | --- |
| [cyanheads/eur-lex-mcp-server](https://github.com/cyanheads/eur-lex-mcp-server) | konektor | CELEX, ELI, ECLI a väzby medzi aktom, novelami, konsolidáciami a transpozíciou. | [eur-lex-guide](https://github.com/cyanheads/eur-lex-mcp-server/blob/19c2200a6b94585f881d1716d8f5cb7513466a40/skills/eur-lex-guide/SKILL.md) |
| [eurostat/PRost](https://github.com/eurostat/PRost) | referencia | Príklady Python a R pre získavanie ukazovateľov a časových radov z Eurostatu. | — |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | knižnica | Oficiálny Python SDK na vytvorenie MCP klienta alebo čítacieho konektora. | — |

## PDF, skeny a prílohy

| Repozitár | Typ | Použitie v TM-Law | Skill |
| --- | --- | --- | --- |
| [docling-project/docling](https://github.com/docling-project/docling) | knižnica | Lokálna extrakcia štruktúry, tabuliek a poradia čítania z komplexných dokumentov. | [docling](https://github.com/docling-project/docling/blob/825c77458b4d05ed7071d0789dc8e40ba9d18211/docling/.agents/skills/docling/SKILL.md) |
| [ocrmypdf/OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | nástroj | Pridanie textovej vrstvy do naskenovaného PDF pre existujúci importér. | — |
| [tesseract-ocr/tessdata_best](https://github.com/tesseract-ocr/tessdata_best) | model | Slovenské jazykové dáta slk.traineddata pre lokálne OCR. | — |
| [jsvine/pdfplumber](https://github.com/jsvine/pdfplumber) | knižnica | Bunky a polohy riadkov v tabuľke PDF s textovou vrstvou. | — |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | knižnica | Konverzia miestnych kancelárskych príloh, napríklad DOCX a XLSX, do Markdownu. | — |

## Vyhľadávanie v korpuse a meranie kvality

| Repozitár | Typ | Použitie v TM-Law | Skill |
| --- | --- | --- | --- |
| [asg017/sqlite-vec](https://github.com/asg017/sqlite-vec) | knižnica | Vektorové vyhľadávanie vedľa existujúceho FTS5. Rozhranie je pred verziou 1.0. | — |
| [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) | knižnica | Viacjazyčný BGE-M3 a rerankery na meranie kvality vyhľadávania v právnom korpuse. | — |
| [qdrant/fastembed](https://github.com/qdrant/fastembed) | knižnica | Lokálne CPU embeddingy cez ONNX. Vhodné na porovnanie latencie a pamäte. | — |
| [huggingface/sentence-transformers](https://github.com/huggingface/sentence-transformers) | knižnica | Embeddingy, CrossEncoder na preusporiadanie pasáží a postupy tréningu. | [train-sentence-transformers](https://github.com/huggingface/sentence-transformers/blob/815cafd2fa997dfdeb50ceae853d6d789e01fe62/skills/train-sentence-transformers/SKILL.md) |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | nástroj | Opakovateľné testy promptov, očakávaných citácií a zmien správania v CI. | [promptfoo-evals](https://github.com/promptfoo/promptfoo/blob/0d4978bace531463ebf200800f396fab9db4c21a/plugins/promptfoo/skills/promptfoo-evals/SKILL.md) |
| [vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas) | knižnica | Metriky pokrytia podkladov a opory odpovede v nájdenom kontexte. | — |
| [isaacus-dev/legal-rag-bench](https://github.com/isaacus-dev/legal-rag-bench) | benchmark | Metodika hodnotenia právneho vyhľadávania a odpovede na vlastných overených otázkach. | — |
