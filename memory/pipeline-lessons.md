# Pipeline lessons

Короткие уроки выпусков. Долговременная память канала — заголовки
`shared/published-titles.md`. Правила Writer отсюда не меняются.

## LESSON-20261006-0647-B232-plan-mode-low-sample
status: proposed
topic_id: B232
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5300 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 148 знаков и не равна title.
- metrika_signal: none — строки B232 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Claude Code: как заставить агента сначала показать план».
- Карточка Дзена отдельно от заголовка: режим плана, список изменений до правок файлов.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261006-1232-B233-together-link-low-sample
status: proposed
topic_id: B233
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 6152 (коридор 2500–6500, до потолка 6500 ещё запас), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 157 знаков и не равна title. Publish PASS, post_id 21031.
- metrika_signal: none — строки B233 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false. Мало данных.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Together Link: как перевести привычного агента на открытые модели».
- Карточка Дзена отдельно от заголовка: переключение кодинг-агента на открытые модели и счёт сессии, не повтор H1.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет. Близость тела к 6500 — одно наблюдение, не повторный провал.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261006-1856-B234-cowork-lid-low-sample
status: proposed
topic_id: B234
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5758 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 166 знаков и не равна title. Publish PASS, post_id 21037. Мало данных.
- metrika_signal: none — строки B234 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Claude Cowork: агент работает с закрытым ноутбуком».
- Карточка Дзена отдельно от заголовка: задачи Pro и Max в облаке, файлы на диске, закрытая крышка не обрывает работу.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261007-0648-B235-dots-computer-low-sample
status: proposed
topic_id: B235
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5940 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 157 знаков и не равна title. Publish PASS, post_id 21043. Мало данных.
- metrika_signal: none — строки B235 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «OpenAI Dots: агент со своим компьютером».
- Карточка Дзена отдельно от заголовка: облачный компьютер и браузер, доступ к ноутбуку выключен.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261007-1851-B237-clef-low-sample
status: proposed
topic_id: B237
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5651 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 145 знаков и не равна title. Publish PASS, post_id 21054. Мало данных.
- metrika_signal: none — строки B237 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Cloudflare Clef: агент выбирает шаг без генерации».
- Карточка Дзена отдельно от заголовка: маршрут за доли секунды и числа вместо длинных рассуждений.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261008-0654-B238-wiki-agents-low-sample
status: proposed
topic_id: B238
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5782 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Description 137 знаков и не равна title. Publish PASS, post_id 21060. Мало данных.
- metrika_signal: none — строки B238 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «OpenAI: агенты перегрузили Википедию — но до реальных статей они НЕ ДОШЛИ».
- Карточка Дзена отдельно от заголовка: миллионы запросов и вопрос, пострадали ли тексты энциклопедии.
- Тело в коридоре гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Требовать все три CTA из канона, пока один maya_pro стабильно проходит гейт.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261008-1258-B239-haiku-low-sample
status: proposed
topic_id: B239
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 6405 (коридор 2500–6500, до hard_fail 6500 осталось 95 знаков), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Title 83 знака при каноне h1 max 70, description 155 и не равна title. Publish PASS, post_id 21066. Мало данных.
- metrika_signal: none — строки B239 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Claude Haiku 5.5: субагент срежет расходы вдесятеро — но длинный запрос ВСЁ УМНОЖИТ».
- Карточка Дзена отдельно от заголовка: десятикратная экономия на рутине и риск пятикратного тарифа на длинном запросе.
- Тело всё ещё внутри коридора гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет. Близость тела к потолку 6500 и title длиннее 70 — одно наблюдение, не повтор.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Поднимать потолок тела или резать заголовок правилом после одного выпуска.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261008-1837-B240-gemini-mail-low-sample
status: proposed
topic_id: B240
category: utility
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 5488 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Title 83 знака при каноне h1 max 70 (второй выпуск подряд после B239), description 144 и не равна title. Publish PASS, post_id 21072. Мало данных.
- metrika_signal: none — строки B240 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «Gemini: агенту завели рабочую почту — но лимит расходов ОСТАНОВИТ проект на полпути».
- Карточка Дзена отдельно от заголовка: личный ящик и диск против внезапной заморозки задач по месячному порогу.
- Тело в середине коридора гейта. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет. Title длиннее 70 повторился (B239 и B240, оба 83), но гейт оба раза PASS и сигнала Метрики нет — потолок h1 в гейт не включать.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Резать заголовок правилом после двух длинных title без выборки и без FAIL гейта.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.

## LESSON-20261008-2055-B241-copilot-sandbox-low-sample
status: proposed
topic_id: B241
category: structure
confidence: low

### Evidence
- artifact: gemini-article-gate.json#status
  finding: PASS, errors пустые, body_visible_chars 6307 (коридор 2500–6500), blockquote 0, CTA только https://t.me/maya_pro (max.ru и kv-ai.ru отсутствуют, гейт всё равно PASS). Title 81 знак при каноне h1 max 70 (третий выпуск подряд после B239=83 и B240=83), description 131 и не равна title. Publish PASS, post_id 21076. Мало данных.
- metrika_signal: none — строки B241 в metrika-latest.json нет (age 0д). Ingest `--days 30` status PASS, rows 211, actionable 0, eligible 2, cohort established, messenger_goal_id null, confidence low. code_status CS_ERR_UNKNOWN, do_not_retry false.

### Named blockers
- LOW_SAMPLE

### Keep
- Имя продукта первым в title: «GitHub Copilot: песочницу открыли — но по умолчанию ваши файлы ВСЁ ЕЩЁ без защиты».
- Карточка Дзена отдельно от заголовка: изоляция в подписке против защиты только после ручного запуска.
- Тело у верхней границы коридора, но внутри него. Один CTA t.me/maya_pro достаточен, пока community-cta PASS.

### Change
- Правила Writer и промпт не менять: выборки по этому выпуску нет, причинности нет. Title длиннее 70 повторился третий раз (B239, B240, B241), гейт каждый раз PASS, сигнала Метрики нет — потолок h1 в гейт не включать.

### Never again
- Судить выпуск по нулевым визитам в день публикации.
- Выводить CTR или дочитывание при code_status CS_ERR_UNKNOWN и отсутствии строки.
- Резать заголовок правилом после трёх длинных title без выборки и без FAIL гейта.

### Proposed apply
- none

### Durable applied
- none

### Resolution
status: recorded
rollback: INSUFFICIENT_DATA — правки правил не вносились, откатывать нечего.
