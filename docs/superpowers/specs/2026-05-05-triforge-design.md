# Triforge — Design Specification

- **Status:** Draft → User review
- **Author:** Claude Opus 4.7 (1M context) для Ильяса (`@ilyasmukiev`)
- **Date:** 2026-05-05
- **Repo (target):** `github.com/ilyasmukiev/triforge`
- **License:** Apache-2.0
- **Brand name:** `triforge` (три инструмента в одном; игра слов с InsForge)

---

## 1. Цель и проблема

Claude Code сегодня страдает тремя ограничениями:

1. **Беспамятство.** Каждый новый чат начинается с чистого листа; контекст прошлых сессий теряется.
2. **Дорогой поиск по коду.** Стандартные `grep + cat` тратят 100k+ токенов там, где умный семантический поиск обошёлся бы 2k.
3. **Нет лёгкого backend-слоя.** Когда агенту нужна БД, файловое хранилище или функции — это всегда ручная настройка.

`triforge` решает все три проблемы одним установщиком, объединяя три зрелых opensource-проекта в когерентную систему:

| Слой | Проект | Лицензия |
|---|---|---|
| 🧠 Память диалогов | **HippoRAG 2** (OSU NLP Group) | Apache-2.0 |
| 🔍 Понимание кода | **semble** (MinishLab) | MIT |
| 🗄 Backend для проектов | **InsForge** (InsForge AI) | Apache-2.0 |

Авторские права на компоненты сохраняются за авторами; `triforge` — это **слой интеграции** под собственной Apache-2.0.

---

## 2. Архитектурные решения (зафиксированы с пользователем)

| # | Развилка | Решение |
|---|---|---|
| Q1 | Как RAG отдаёт память агенту | **Гибрид**: SessionStart-prelude + MCP-tool `rag_search` |
| Q2 | Что сохраняется в RAG | **Raw-диалог** (без tool calls / thinking) **+ summary** |
| Q3 | LLM для OpenIE в HippoRAG | **Auto-fallback**: `ANTHROPIC → OPENAI → Ollama → dense-only` |
| Q4 | Где хранится RAG-база | **Локально по умолчанию**, опция `--storage=insforge` |
| Q5 | Идентичность проекта | `triforge` / `ilyasmukiev` / Apache-2.0 |
| Q6 | Хук захвата чатов | **Гибрид**: `Stop` → JSONL log; `SessionEnd` → фоновый индексер |
| Q7 | Privacy layer | **Гибрид**: regex first-pass + heuristic-triggered LLM cleaner subagent |

---

## 3. Архитектура — три слоя

```
                      ┌──────────────────────────────────────────┐
                      │             Claude Code (CLI)             │
                      │  ~/.claude.json (глобально, auto-load)    │
                      └────┬──────────────┬───────────────┬──────┘
                           │              │               │
                  ┌────────▼──┐  ┌────────▼────┐  ┌──────▼──────────┐
                  │  semble   │  │  InsForge   │  │ triforge-memory │
                  │  (MCP)    │  │  (MCP)      │  │     (MCP)       │
                  │  CODE     │  │  BACKEND    │  │  CHAT MEMORY    │
                  └────┬──────┘  └──────┬──────┘  └────────┬────────┘
                       │                │                  │
                  ┌────▼─────┐    ┌─────▼──────┐   ┌──────▼──────────┐
                  │ in-mem   │    │ Postgres   │   │ ~/.claude/      │
                  │ index по │    │ + pgvector │   │   triforge/     │
                  │ коду     │    │ (опц.)     │   │   {project}/    │
                  │ проекта  │    │            │   │   ├─ chats.jsonl│
                  └──────────┘    └────────────┘   │   ├─ kg.pkl     │
                                                   │   ├─ vectors/   │
                                                   │   └─ summary.md │
                                                   └─────────────────┘

                          ┌───────────────────┐  ┌───────────────────┐
                          │ Hooks (per-project)│  │ /rag (skill, ман.) │
                          │ SessionStart →    │  │ Запускается раз:   │
                          │   prelude из summ.│  │ 1. поднимает MCP   │
                          │ Stop → JSONL log  │  │ 2. пишет AGENTS.md │
                          │ SessionEnd → бг   │  │ 3. ставит хуки     │
                          │   индексер        │  │    в .claude/      │
                          └───────────────────┘  └───────────────────┘
```

**Принципы:**
- Три MCP-сервера, **независимых**: каждый можно отключить/обновить отдельно.
- semble и InsForge всегда «спят» в проекте до прямого вызова → нулевая стоимость холостого хода.
- `triforge-memory` всегда зарегистрирован, но **per-project активация** через файл-маркер `.triforge/config.json`. Без него — read-only-no-op.

---

## 4. Поток данных

### 4.1 CAPTURE (мгновенно, после каждого ответа агента)

- Хук: **`Stop`**.
- Действия:
  1. Извлечь из transcript Claude Code последние user/assistant пары.
  2. Удалить tool calls, thinking блоки.
  3. Прогнать через **Privacy layer**:
     - **Regex first-pass:** `.triforge/exclude.txt` + встроенные паттерны (`API_KEY=...`, `Bearer ...`, JWT, `password\s*[:=]`, `[A-Z_]+_TOKEN=...`, e-mail, абс. пути с `/Users/`, `/home/`).
     - **Heuristic trigger LLM cleaner:** если в очищенном тексте всё ещё встречаются триггер-слова (`secret`, `token`, `password`, `auth`, `private_key`, `bearer`), вызвать subagent с дешёвым LLM (Q3-fallback) и промптом «redact any sensitive strings, replace with `[REDACTED]`».
  4. Append записи в `~/.claude/triforge/{sha256(абс_путь_проекта)[:12]}/chats.jsonl`:
     ```jsonl
     {"ts": "2026-05-05T18:00:00Z", "session_id": "...", "role": "user", "text": "..."}
     {"ts": "2026-05-05T18:00:05Z", "session_id": "...", "role": "assistant", "text": "..."}
     ```
- **Без LLM-вызова на этом шаге** (кроме редкого privacy-trigger). Латенция захвата < 50 мс.
- **Без блокировки UX:** запись в файл синхронная, дальнейшая обработка асинхронная.

### 4.2 INDEX (фоновый, после завершения сессии)

- Хук: **`SessionEnd`** запускает `triforge index --project=$CWD --background &`.
- Дочерний процесс (Python, asyncio):
  1. Читает `chats.jsonl`, сравнивает с `state.json` (`last_indexed_offset`).
  2. Для каждой новой пары user/assistant:
     - **Summary:** LLM (Q3-fallback) делает короткое (≤ 200 слов) резюме «о чём диалог, какое решение принято, какие файлы затронуты». Append в `summary.md`.
     - **HippoRAG OpenIE:** LLM извлекает триплеты `(subject, relation, object)`, обновляет NetworkX-граф `kg.pkl`.
     - **Dense embeddings:** через `model2vec/potion-multilingual-128M` (статика, без API), append в `vectors/{N}.parquet`.
  3. Обновляет `state.json` → `last_indexed_offset`.
- **Dense-only fallback:** если все LLM в Q3-цепочке недоступны, summary и OpenIE пропускаются; пишутся только embeddings. `rag_search` работает на cosine + BM25, без PPR.
- **Идемпотентность:** запись по hash чанка, повторный запуск не дублирует.
- **Бэкоф при ошибках:** 3 ретрая, экспоненциальная задержка; при фейле — лог в `~/.claude/triforge/{hash}/errors.log`, следующий `SessionEnd` попробует снова.

### 4.3 RETRIEVE (два пути, гибрид)

#### Путь A — автоматический prelude

- Хук: **`SessionStart`**.
- Действия:
  1. Прочитать `~/.claude/triforge/{hash}/summary.md`.
  2. Взять последние ~500 слов (по символам ~3500).
  3. Вернуть JSON с полем `additionalContext` — Claude Code инжектит в системный промпт.
- Если `summary.md` пуст или отсутствует `.triforge/config.json` → no-op.

#### Путь B — MCP-инструмент `rag_search`

- Сервер: **triforge-memory** (FastMCP, stdio transport).
- Tool signature:
  ```python
  rag_search(
      query: str,
      top_k: int = 5,
      mode: Literal["hybrid", "graph", "dense", "bm25"] = "hybrid",
      project_path: Optional[str] = None,  # default: cwd
  ) -> list[Chunk]
  ```
- **Hybrid mode** (default): RRF fusion трёх источников:
  1. **PPR по графу** (HippoRAG) — multi-hop reasoning.
  2. **Cosine по embeddings** (vicinity).
  3. **BM25 по raw chats.jsonl** (bm25s).
- Возвращает чанки с метаданными: `{text, role, ts, session_id, score, source}`.

---

## 5. Установка и UX

### 5.1 Однократная установка на машину

```bash
$ pipx install triforge
$ triforge install
```

Что делает `triforge install`:

1. Регистрирует **три MCP-сервера** в `~/.claude.json`:
   ```json
   {
     "mcpServers": {
       "semble": { "command": "uvx", "args": ["--from", "semble[mcp]", "semble"] },
       "insforge": { "type": "http", "url": "https://mcp.insforge.dev/mcp" },
       "triforge-memory": { "command": "triforge-memory", "args": ["--serve"] }
     }
   }
   ```
2. Дописывает в `~/.claude/CLAUDE.md` секции:
   - «Three MCPs auto-loaded» — короткое описание для будущих агентов.
   - «Triforge memory rules» — что делать, если в проекте есть `.triforge/`.
3. Регистрирует глобальный slash-command `~/.claude/commands/rag.md`.
4. Создаёт `~/.claude/triforge/` (корень кеша моделей и проектных баз).
5. **Не требует API-ключей** — работает в dense-only режиме. Если есть `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` в окружении — auto-detect.

### 5.2 Активация в проекте

```bash
$ cd ~/my-project && claude
> /rag
```

Slash-command делает:

1. `mkdir .triforge/`
2. `write .triforge/config.json` (storage=local, llm=auto, exclude=[]).
3. `append .triforge/.gitignore` (защита, если папка случайно добавлена в git).
4. `append AGENTS.md` (или создать; fallback на `CLAUDE.md`):
   ```markdown
   ## Triforge memory
   This project uses triforge-memory. Your replies are saved into a
   per-project graph memory; you can search past conversations via the
   MCP tool `rag_search`.
   ```
5. `write .claude/settings.local.json` — три хука:
   ```json
   {
     "hooks": {
       "SessionStart": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "triforge prelude --project=$CWD" }] }],
       "Stop":         [{ "matcher": "*", "hooks": [{ "type": "command", "command": "triforge capture --project=$CWD" }] }],
       "SessionEnd":   [{ "matcher": "*", "hooks": [{ "type": "command", "command": "triforge index --project=$CWD --background" }] }]
     }
   }
   ```
6. Сообщить пользователю «Память активирована».

### 5.3 Управление

```
triforge status    [--project=PATH]   статистика: chunks, graph nodes, size
triforge dump      [--project=PATH]   распечатать summary.md
triforge purge     [--project=PATH]   очистить память проекта
triforge migrate   --to=insforge      перенести локальный store в InsForge
triforge update                       обновить semble/insforge/HippoRAG
triforge uninstall                    откатить ~/.claude.json и commands/rag.md
```

---

## 6. Структура репозитория

```
triforge/
├── README.md                       (с разделами: Why, Install, How it works, Credits)
├── LICENSE                         Apache-2.0
├── NOTICE                          обязательный для Apache-2.0
├── pyproject.toml                  Python ≥ 3.10
├── CHANGELOG.md
├── CONTRIBUTING.md
├── .github/workflows/
│   ├── ci.yml                      pytest + mypy + ruff
│   ├── publish.yml                 PyPI release on tag
│   └── docs.yml                    mkdocs-material → gh-pages
├── src/triforge/
│   ├── cli.py                      install / status / dump / purge / migrate
│   ├── installer.py                writes ~/.claude.json, CLAUDE.md, commands/
│   ├── memory/
│   │   ├── server.py               MCP server (FastMCP) — tool rag_search
│   │   ├── capture.py              Stop hook entry-point
│   │   ├── prelude.py              SessionStart hook entry-point
│   │   ├── indexer.py              SessionEnd background daemon
│   │   ├── hipporag_adapter.py     wraps hipporag, incremental ops
│   │   ├── llm.py                  auto-fallback chain
│   │   ├── privacy.py              regex + heuristic LLM cleaner
│   │   ├── storage_local.py        SQLite/parquet/NetworkX
│   │   └── storage_insforge.py     pgvector via InsForge MCP
│   ├── skills/rag.md               slash-command body
│   └── templates/
│       ├── AGENTS_section.md
│       ├── settings.local.json
│       └── triforge_config.json
├── tests/
│   ├── test_installer.py
│   ├── test_capture.py
│   ├── test_privacy.py
│   ├── test_indexer.py
│   ├── test_llm_fallback.py
│   ├── test_rag_search.py
│   └── fixtures/
├── docs/
│   ├── index.md
│   ├── install.md
│   ├── architecture.md
│   ├── privacy.md
│   ├── insforge-mode.md
│   ├── troubleshooting.md
│   └── credits.md
├── benchmark/                       ← обязательный gate (см. §7)
│   ├── README.md
│   ├── scenarios/
│   │   ├── baseline-no-triforge/
│   │   └── with-triforge/
│   ├── tasks.md                    набор задач для прогона
│   ├── run_benchmark.py            автоматизированный прогон
│   └── results/
│       ├── 2026-05-05-comparison.md
│       └── raw/
└── examples/
    ├── 01-quickstart.md
    ├── 02-multi-project.md
    └── 03-self-hosted-insforge.md
```

---

## 7. Сравнительный benchmark (mandatory gate перед публикацией)

**Перед `git push` финального релиза** прогоняем сравнительный тест на маленьком проекте.

### 7.1 Тестовый проект

`benchmark/sandbox-todo-app/` — мини TODO-приложение (Python Flask, ~200 строк, 5 файлов: `app.py`, `models.py`, `db.py`, `templates/`, `tests/`).

### 7.2 Сценарии

**Сценарий A (baseline):** чистый Claude Code без triforge.

**Сценарий B (triforge):** установлены три MCP, в проекте выполнен `/rag`.

### 7.3 Тестовые задачи (4 задачи, по 2 сессии каждая)

| # | Сессия 1 | Сессия 2 (новый чат) | Что проверяем |
|---|---|---|---|
| 1 | «Добавь endpoint `/done` для отметки задачи выполненной» | «Какое решение мы приняли по статусам задач?» | **Память: помнит ли решение?** |
| 2 | «Найди функцию обработки ошибок» | (только сессия 1) | **Code search: токены, точность** |
| 3 | «Реализуй PATCH /tasks/{id} с валидацией. Используй те же подходы, что и в POST.» | (только сессия 1) | **Code search: качество references** |
| 4 | «Объясни архитектуру проекта» | «Что мы решили про слой данных?» | **Multi-hop память** |

### 7.4 Метрики

| Метрика | Как измеряем |
|---|---|
| **Токены ввода/вывода** | из API-ответов Claude (tracked в `usage`) |
| **Latency time-to-first-token** | timestamp в logs |
| **Latency total** | timestamp в logs |
| **Качество ответа** | manual rubric 1-5 (correctness, references to past, completeness) |
| **Recall на «памятных» вопросах** | бинарно: помнит / не помнит конкретное решение |
| **Disk footprint** | `du -sh .triforge/ ~/.claude/triforge/{hash}` |

### 7.5 Формат отчёта

`benchmark/results/2026-05-05-comparison.md`:
```markdown
# Triforge vs Baseline — Comparative Benchmark

| Task | Baseline tokens | Triforge tokens | Δ% | Baseline quality | Triforge quality |
|---|---|---|---|---|---|
| 1 | XX,XXX | X,XXX | -YY% | 2/5 | 5/5 |
| ... | ... | ... | ... | ... | ... |

**Verdict:** triforge экономит N% токенов и даёт +M пунктов качества памяти.
```

### 7.6 Gate

**Если triforge не показал измеримой пользы хотя бы в одной из категорий (память ИЛИ токены) — публикация откладывается, дизайн пересматривается.**

---

## 8. Кредиты (NOTICE + README + docs/credits.md)

Apache-2.0 требует `NOTICE` с атрибуцией. Включаем:

- **semble** — Thomas van Dongen (`@Pringled`), Stéphan Tulkens (`@stephantul`); MinishLab/minish.ai; MIT.
- **InsForge** — InsForge AI, Inc.; Apache-2.0.
- **HippoRAG 2** — OSU NLP Group (Ohio State University); Apache-2.0; papers NeurIPS'24 + ICML'25.
- **Inspiration article** — rRenegat, RUVDS, «Ваш RAG не умеет думать. А мой умеет», Habr, 2025-04-24.

В README — раздел «Acknowledgments» с описанием роли каждого проекта.

---

## 9. Тестирование

- **Unit** (`tests/`): mock LLM, mock filesystem, проверяем capture/indexer/privacy/fallback.
- **Integration** (`tests/integration/`, помечены `@pytest.mark.slow`): реальный HippoRAG на 3-х фейковых чатах, реальный rag_search.
- **CI:** на PR — только unit; nightly — slow.
- **Benchmark** (`benchmark/`): не в CI, ручной прогон перед релизом.

---

## 10. Релиз и публикация

1. Все unit-тесты зелёные.
2. Slow-тесты зелёные (хотя бы один прогон).
3. **Benchmark показал измеримую пользу** (см. §7.6).
4. CHANGELOG.md обновлён.
5. Tag `v0.1.0` → GitHub Action собирает wheel и публикует на PyPI.
6. README на главной странице репо корректно рендерит таблицу преимуществ.

---

## 11. Открытые вопросы / TODO для следующего этапа

- Конкретный prompt для **summary** (нужен короткий, инструктивный, с ограничением 200 слов).
- Конкретный prompt для **OpenIE** (заимствуем из HippoRAG или адаптируем).
- Конкретный prompt для **privacy LLM cleaner**.
- Параметры RRF fusion (веса `α/β/γ`).
- Пороги heuristic-trigger для privacy.
- Решение по `model2vec` модели для русского/смешанного контента (потенциально `potion-multilingual-128M`).

Эти детали уйдут в implementation plan.

---

## 12. Cross-platform support

Поддерживаемые ОС: **macOS**, **Linux**, **Windows**.

Принципы:
- Все пути — через `pathlib.Path`, никаких хардкод-сепараторов.
- User data: `~/.claude/triforge/` (не `platformdirs`) для соответствия Claude Code конвенции; на Windows это `%USERPROFILE%\.claude\triforge\`.
- Hooks-команды в `.claude/settings.local.json` используют **абсолютный путь к `triforge` исполняемому файлу** (определяется при `triforge install`), а не shell-переменные — чтобы избежать `$CWD` vs `%CWD%`. Project path передаётся явно через флаг `--project=<path>`, который Claude Code подставит как `${CLAUDE_PROJECT_DIR}` (поддерживается на всех платформах).
- Background daemon (`triforge index --background`):
  - Unix: `os.fork()` или `subprocess.Popen(..., start_new_session=True)`.
  - Windows: `subprocess.Popen(..., creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)`.
- File locking: `portalocker` (cross-platform) для concurrent-safe записи в `chats.jsonl` и `state.json`.
- CI matrix: `ubuntu-latest`, `macos-latest`, `windows-latest` на трёх версиях Python (3.10, 3.11, 3.12).

Все примеры команд в README и docs даются для Bash и PowerShell.

---

## 13. Не входит в MVP (out of scope)

- Multi-user shared memory.
- Веб-UI для просмотра памяти.
- Экспорт памяти в Notion/Obsidian.
- Поддержка Claude Desktop (только Claude Code CLI).
- Автоматическая миграция между версиями HippoRAG (manual update на старте).
