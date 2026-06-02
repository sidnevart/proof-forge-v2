---
name: progress
description: |
  Show learning progress toward expert mastery — per-concept badges + what's left.
  Use this skill ALWAYS when:
  — user asks "прогресс", "сколько я отработал", "далеко ли до эксперта", "мой уровень"
  — user wants to know what to practice next
  — after a session, to show measurable progress
  Triggers: "прогресс", "сколько я отработал", "далеко ли до эксперта", "мой уровень", "что дальше учить", "progress"
---

# Progress

Показываешь измеримый прогресс к уровню эксперта. «Эксперт по теме» = все ключевые концепты на 🟦 explain. Опираешься на mastery-движок (backend считает уровни детерминированно).

---

## Шаг 1: Загрузи прогресс

```
get_mastery_progress(topic)   # topic опционально — без него по всем темам
get_next_focus(topic)         # что отрабатывать дальше
```

---

## Шаг 2: Покажи прогресс

Формат:

```
📊 Прогресс: [тема или «все темы»]

Концепты:
🟦 closures            — explain (3 практики, качество 0.82)
🟩 lexical scope       — apply   (2 практики, качество 0.71)
🟨 closure memory      — recognize (только теория, нужна практика)
🟥 ic capture by ref   — not started

Итого: 1 из 4 на 🟦 expert · 2 на 🟩 apply+ · отработано 7 практик · среднее качество 0.76

🎯 До эксперта по теме осталось:
- lexical scope: нужно задание difficulty 3 + struggle-check
- closure memory: нужно ≥2 практики уровня apply
- ic capture by ref: начни с теории

Следующий фокус: [из get_next_focus] — [concept] [badge], [reason]
```

---

## Шаг 3: Предложи действие

В зависимости от состояния:
- Есть 🟥/🟨 концепты → предложи `"помоги изучить <следующий фокус>"`
- Все на 🟩, нужен 🟦 → предложи `"review"` с заданиями посложнее
- Все на 🟦 → поздравь, тема освоена на эксперта; предложи смежную тему

---

## Правила

- Бейджи и пороги берутся из backend — не выдумывай уровни, показывай как пришло из `get_mastery_progress`
- Всегда показывай **что конкретно блокирует expert** и **что делать дальше** — прогресс без следующего шага бесполезен
- Если данных нет (`total_concepts == 0`) — скажи что обучение ещё не начато, предложи `"помоги изучить <тема>"`
