# Adaptive Pre-Topic Onboarding (Interview → Study Profile)

**Date:** 2026-06-07
**Status:** Design approved, pending spec review
**Supersedes:** the static 4-card strategy presets shipped in the domain/strategy work (commit 308845d)

---

## Context

We recently shipped per-topic **domain adaptation** + **strategy presets**: a topic
is classified into a domain, and the learner picks one of 4 preset cards
(Deep dive / Practical sprint / Exam cram / Gentle intro) that parametrize conspect,
tasks, and chat. The user's critique: **presets are still templates** — a fixed
shape applied to every topic — which is exactly the rigidity we set out to remove.

The desired behavior is modeled on the `study-mentor-v2` Claude skill: before writing
anything, the mentor asks a **small number of important questions whose content is
generated from the actual topic and materials** (topic checkboxes → knowledge check →
format), then proposes a plan, then generates. Crucially: **answer quality of the
conspect and tasks must NOT drop** — the interview changes *format, focus, and
emphasis*, never the quality bar.

This spec replaces the preset cards with an **adaptive, chat-styled pre-topic
interview** that produces a richer **StudyProfile**, which feeds the existing
generation pipeline (conspect + tasks) and the mentor chat — answering the user's
two questions at once: flexibility in *conspecting* and in *chat*, from one source
of truth.

### Confirmed decisions (from brainstorming)

1. **Question source — hybrid.** A fixed backbone of 5 slots; the AI generates the
   *options/content* of each slot per topic + domain + materials. Deterministic
   fallback (domain-derived generic options) when no LLM.
2. **Answer modes.** Each slot offers AI-generated option chips (multi-select where
   it fits) **and** a always-present "Свой ответ" free-text field.
3. **UX — chat-style (native).** The interview is a chat-styled exchange on the
   topic-start screen, with a small progress hint ("2/5") and a persistent
   "Пропустить →". (Chosen over a full-screen wizard; wizard's progress + skip ideas
   folded in.)
4. **Plan before writing.** After the slots, the AI shows one short plan bubble
   ("вот что напишу…") with **Поехали / Поправить**, then generates.
5. **Presets retired from UI.** The 4 preset cards are removed. The interview is the
   main path. **Skip → balanced default** (today's `deep_dive` profile lives on
   internally as the fallback). No "quick-start presets" surface.
6. **Delivery — dedicated isolated unit** (`study_onboarding`), separate from the
   persistent mentor chat. It owns the interview and hands a resolved StudyProfile to
   the existing `POST /study-sessions` generation. Does not pollute chat history.
7. **No task-count cap.** The generator produces as many practice tasks as needed to
   consolidate the focus concepts — not a fixed theory+practice pair.
8. **No separate time slot.** Its only independent effect (practice volume) is
   already covered by "enough tasks to consolidate"; a 6th question isn't worth it.

---

## Architecture & Data Flow

A new isolated unit `study_onboarding` (backend service + router + a chat-styled
frontend component) produces a **StudyProfile**, the single hand-off object into the
unchanged generation pipeline.

The flow is **stateless** — no server-side interview session. The frontend holds the
answers and sends them in one batch. Two onboarding endpoints, then the existing
session-creation endpoint.

```
User opens topic-start screen
  → POST /api/onboarding/questions { topic_id, user_id }
        → classify domain now (reuse domain_classifier);
          AI builds each slot's options from topic + materials + domain
          (deterministic domain-derived fallback when no LLM)
        → returns { domain, slots }
  ↓  chat-styled: mentor asks slot-by-slot; chips + "Свой ответ"; progress "n/5";
     "Пропустить" anytime. Answers accumulate CLIENT-SIDE.
  → POST /api/onboarding/plan { topic_id, user_id, answers }
        → build_study_profile(answers); AI returns short plan text;
          persist the resolved profile to topics.strategy_config
        → returns { plan_md, study_profile }
  ↓  user: Поехали | Поправить (jump back to a slot, edit, re-request plan)
  → POST /api/study-sessions { topic_id, user_id, study_profile }    ← EXISTING endpoint, richer profile
        → conspect + tasks generation (existing pipeline, profile-driven)
        → profile injected into mentor-chat system prompt
  → redirect /study/{session_id}  (conspect streams via existing SSE)
```

The Skip path bypasses both onboarding calls: it goes straight to
`POST /study-sessions` with no `study_profile`, which resolves to the balanced default.

### Unit boundaries

- **`app/services/study_onboarding.py`** — owns the slot backbone, AI option
  generation, plan synthesis, and `build_study_profile(answers)`. Depends only on
  `llm_utils` and `domain_profiles`. Fully testable with a mocked LLM.
- **`app/routers/onboarding.py`** — two endpoints: `POST /onboarding/questions`
  (classify domain + build slots) and `POST /onboarding/plan` (build profile +
  synthesize plan + persist to the topic). Stateless: answers arrive from the client
  in the plan call; nothing is held server-side between calls.
- **StudyProfile** — the hand-off object, a superset of today's `strategy_config`.
  Stored in the **existing `topics.strategy_config` JSON column** (richer shape, no
  new migration). Shape:
  ```json
  {
    "goal": "interview | understand | refresh | solve_task",
    "known_concepts": ["..."],
    "focus_subtopics": ["..."],
    "conspect_format": { "depth": "...", "include_diagrams": true, "analogy_density": "..." },
    "task_format": ["code", "mini_project", "..."],
    "depth": "brief | moderate | comprehensive",
    "difficulty": "gentle | standard | challenging"
  }
  ```
  `resolve_strategy()` (existing) is extended to read this superset; unknown keys are
  ignored, missing keys inherit the balanced (`deep_dive`) default — so old topics and
  the Skip path both resolve cleanly.
- **Generation pipeline** — interface unchanged. `practice_generation.py` already takes
  `(profile, strategy)`; it reads the new fields and ignores the rest.
- **Mentor chat** — `_build_topic_context` injects the same profile lines, so chat
  adaptivity comes from the *same* StudyProfile, not a parallel mechanism.

### Quality guarantee

The profile changes only **format / focus / emphasis**. The mandatory conspect
structure (Prerequisites at top, Glossary at end, section rhythm) and the task
difficulty ladder are untouched. Known concepts are **compressed, never dropped**, so
the conspect stays self-contained. The interview steers *what to emphasize and how to
present* — never *how good*.

---

## The Interview Backbone (5 slots, ≤10 questions)

Structure is fixed; the AI fills each slot's options per topic + domain + materials.
Every slot has option chips **and** a "Свой ответ" field. Slot order = chat order.

| # | Slot | AI-generated options (examples) | Maps to |
|---|------|----------------------------------|---------|
| 1 | **Цель** | "Понять с нуля / Освежить / Подготовка к собесу / Решить задачу" | `goal` → depth + difficulty + task slant |
| 2 | **Что уже знаешь** (multi-select) | concrete concepts from the material — "Базовый синтаксис каналов", "select/deadlock" | `known_concepts[]` → compress in conspect; chat won't re-explain |
| 3 | **Фокус** (multi-select) | subtopics found in the material | `focus_subtopics[]` → emphasize in conspect + tasks |
| 4 | **Формат конспекта** | domain-appropriate: depth, examples, diagrams on/off, analogy density | `conspect_format` knobs |
| 5 | **Формат заданий** | **domain-aware** via existing `domain_profiles` — coding→code/mini-project/interview; language→dialogues/grammar; etc. | `task_format` → task recipe selection |

- **Adaptive count.** For a trivial topic or one with no materials, the AI may return
  only slots 1, 4, 5 (it decides how many slots/options are meaningful, never
  exceeding the 5-slot frame). Quick topic = 2-3 questions; rich topic = 5.
- **Deterministic fallback.** With no LLM, each slot falls back to generic
  domain-derived options from `domain_profiles`, so the flow runs headless (CI/dev).

### Mapping into generation (quality stays high)

`_build_conspect_prompt` / `_build_tasks_prompt` gain three injected lines, on top of
the existing mandatory structure:
- *"Ученик уже владеет: {known_concepts} — упомяни кратко, не разжёвывай."*
- *"Сделай акцент на: {focus_subtopics}."*
- *"Цель ученика: {goal}."*

**Task count is not fixed.** The tasks prompt is told to produce **one practice task
per focus area, plus a capstone when goal is interview/deep** — as many as needed to
consolidate the focus concepts. The theory task stays; practice tasks scale to
coverage. This replaces today's hardcoded theory+practice pair.

---

## UX Flow

One chat-styled screen at the topic-start step (`/topics/[id]` start action and the
new-topic flow's final step), three states:

1. **Asking** — mentor bubbles slot-by-slot; chips (multi-select where it fits) +
   "Свой ответ"; small progress "n/5"; persistent "Пропустить →" (→ balanced default
   → straight to generation).
2. **Plan** — one mentor bubble summarizing what will be written ("фокус на X,
   пропущу Y, задания: код + мини-проект уровня собес"). Buttons **Поехали /
   Поправить** (Поправить jumps back to the relevant slot).
3. **Generating** — Поехали → `practice.startSession(userId, topicId, profile)` →
   redirect to `/study/[sessionId]`, where the conspect already streams via the
   existing SSE flow.

The 4 preset cards are removed from `topics/new/page.tsx` and `topics/[id]/page.tsx`;
the interview component replaces them.

---

## Error Handling & Resilience (never block learning)

- **No LLM (CI/dev):** questions = deterministic domain-derived options; plan =
  templated summary; generation falls back as today. Whole flow works headless.
- **LLM error mid-interview:** silently resolve to the balanced default and proceed to
  generation — never strand the user.
- **Skip at any point:** `POST /study-sessions` with no `study_profile` → balanced
  default → straight to generation.
- **Dropped connection:** both onboarding calls are idempotent and stateless; answers
  live client-side until the Plan call, and the profile is persisted only at the Plan
  step, so a mid-interview drop loses nothing on the server.

---

## Testing

**Unit (`tests/backend/unit/`):**
- `build_study_profile(answers)` maps each slot correctly, including free-text answers.
- Deterministic question fallback returns valid slots per domain with no LLM.
- Plan fallback returns a templated summary with no LLM.
- Task-count scaling: more focus concepts → more practice tasks (prompt assertion).
- `resolve_strategy()` reads the StudyProfile superset; missing keys inherit defaults.

**Integration (`tests/backend/integration/`):**
- `POST /onboarding/questions` classifies domain and returns the slot set (fallback
  options with no LLM).
- `POST /onboarding/plan` builds + persists the resolved profile onto the topic and
  returns a plan (templated with no LLM).
- `POST /study-sessions` with a `study_profile` stores it and feeds generation
  (assert profile reflected in `topics.strategy_config`).
- Skip path (`POST /study-sessions` with no profile) → balanced default → session
  still generates (fallback tasks).

**Frontend:** `tsc --noEmit` + `next build` clean; manual: run a topic through the
chat interview, confirm plan bubble, confirm conspect reflects focus/known answers.

---

## Out of Scope (explicitly)

- Auto-generating strategy recommendations from learner history (still deferred —
  the event-logging groundwork from the prior work feeds this later).
- Persisting interview transcripts as chat history (onboarding state is ephemeral).
- Changing the mandatory conspect structure or the SSE streaming mechanism.
