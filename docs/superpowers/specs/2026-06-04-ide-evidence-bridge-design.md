# IDE Evidence Bridge Design

Date: 2026-06-04

## Summary

Proof Forge should not become a learning IDE. It should remain the learning system that creates study artifacts, guides active learning, verifies user work, and stores learning memory.

The new feature is an IDE Evidence Bridge. During a study session, Proof Forge gives the user theory tasks, practice tasks, and mini-project work. When a task requires real project files, the user solves it in JetBrains. The plugin sends the solution evidence back to Proof Forge without manual copy-paste, zip uploads, or folder transfer.

The IDE is the workbench. Proof Forge is the learning memory and verification layer.

## Product Boundary

Proof Forge owns:

- topic start and learning session state;
- conspect generation;
- theory and practice task generation;
- mini-project task instructions and expected evidence;
- submitted evidence storage;
- deterministic and AI evaluation;
- follow-up questions;
- mastery, weak spots, review cards, and later capsule generation.

The JetBrains plugin owns:

- account connection;
- active task selection;
- local project/folder detection;
- file or diff preview before submission;
- configured check command execution or output capture;
- evidence submission;
- evaluation status display and a link back to Proof Forge.

The plugin is not a second learning app. It should not include the full mentor UI, capsule reader, chat, complex scaffolding, package management, or agentic code modification in v1.

## Correct Learning Flow

The capsule is not the source of the first mini-project. It is generated after a learning segment and becomes memory for later review and continued study.

V1 learning flow:

1. User starts a topic in Proof Forge.
2. Proof Forge generates a conspect and learning plan.
3. Proof Forge creates theory and practice tasks during the active study session.
4. Some practice tasks are marked as IDE tasks when they require real files or a project.
5. User opens JetBrains and solves the task locally.
6. JetBrains plugin submits evidence to Proof Forge.
7. Proof Forge evaluates the submission.
8. Proof Forge asks follow-up questions when needed.
9. Proof Forge updates mastery, weak spots, and review cards.
10. When the user finishes a learning segment, Proof Forge forges a capsule from the conspect, completed tasks, mistakes, submitted code evidence, and follow-up answers.

Learning on the same topic may continue after a capsule exists. Later evidence should be attached to the same topic and can inform future capsules or capsule updates.

## Core Entities

### StudySession

An active learning process for a topic. It contains the current conspect, generated tasks, submitted evidence, follow-ups, and progress signals.

Key fields:

- `id`
- `user_id`
- `topic_id`
- `status`: active, paused, completed
- `conspect_md`
- `learning_goals`
- `created_at`
- `completed_at`

### PracticeTask

A task inside a study session. It can be a theory question, written explanation, coding task, debugging task, or mini-project task.

Key fields:

- `id`
- `study_session_id`
- `topic_id`
- `type`: theory, written, coding, debugging, mini_project
- `title`
- `instructions_md`
- `target_concepts`
- `difficulty`
- `expected_evidence`
- `check_commands`
- `status`: assigned, opened_in_ide, submitted, evaluated, needs_revision, completed

### IdeSession

A connection between a user account and an installed IDE plugin.

Key fields:

- `id`
- `user_id`
- `ide`: jetbrains
- `ide_product`: IntelliJ IDEA, PyCharm, WebStorm, GoLand, or unknown
- `plugin_version`
- `paired_at`
- `last_seen_at`

### IdeSubmission

The evidence sent from the IDE for a practice task.

Key fields:

- `id`
- `practice_task_id`
- `user_id`
- `ide_session_id`
- `files`
- `diff`
- `test_output`
- `check_command`
- `exit_code`
- `reflection`
- `language`
- `submitted_at`

### Evaluation

The result of checking a submission.

Key fields:

- `id`
- `submission_id`
- `score`
- `status`: passed, needs_revision, failed
- `feedback_md`
- `concept_scores`
- `weak_spots`
- `next_action`
- `created_at`

### FollowUp

One or more verification questions after a submission.

Key fields:

- `id`
- `evaluation_id`
- `question`
- `expected_answer`
- `user_answer`
- `score`
- `feedback_md`

### Capsule

The post-session learning memory artifact. It should include what the user studied, the final conspect, important mistakes, completed tasks, code evidence summary, weak spots, review questions, and next steps.

## Practice Bridge API

The API should be IDE-agnostic so JetBrains is the first client, not the only possible client.

Suggested endpoints:

- `POST /api/study-sessions`
  Start a learning session for a topic.

- `GET /api/study-sessions/{id}`
  Load session state, conspect, tasks, and progress.

- `POST /api/study-sessions/{id}/tasks/generate`
  Generate theory and practice tasks for the current session.

- `GET /api/practice-tasks?status=active`
  Let a plugin list active tasks for the authenticated user.

- `GET /api/practice-tasks/{id}`
  Fetch task instructions, expected evidence, and optional check commands.

- `POST /api/ide-sessions/pair`
  Pair the JetBrains plugin with a Proof Forge account.

- `POST /api/practice-tasks/{id}/submissions`
  Submit files, diff, test output, command output, and reflection from the IDE.

- `POST /api/submissions/{id}/evaluate`
  Evaluate the submission and store the result.

- `POST /api/follow-ups/{id}/answer`
  Store a follow-up answer and update learning state.

- `POST /api/study-sessions/{id}/complete`
  Complete a learning segment and forge a capsule.

## JetBrains Plugin V1

The first plugin should target the IntelliJ Platform, with IntelliJ IDEA as the first tested product. Later testing can expand to PyCharm, WebStorm, and GoLand.

V1 plugin flow:

1. User installs the plugin.
2. User pairs the plugin with Proof Forge.
3. Plugin lists active IDE tasks from the user account.
4. User selects a task.
5. Plugin shows task instructions in a tool window or panel.
6. User chooses current project/folder as the solution source.
7. Plugin previews files or diff to submit.
8. Plugin runs the configured check command when available, or lets the user paste/select command output.
9. User submits evidence.
10. Plugin shows evaluation status and a link to the full Proof Forge result.

V1 should avoid:

- generating full local projects automatically;
- managing dependencies;
- replacing the IDE terminal;
- modifying user code;
- embedding the complete Proof Forge learning UI.

## Evaluation Model

Evaluation should combine three signals.

### Deterministic Evidence

Use test output, exit code, command logs, and changed files to understand whether the solution works.

### AI Review

Review the submitted files or diff against the task goal, expected concepts, and rubric. This should catch hardcoding, missing edge cases, poor abstraction, and misunderstood concepts.

### Follow-Up Verification

Ask 1-2 questions after the submission when the system needs confidence that the user understands the solution. Tests are evidence, not proof of learning.

Evaluation output:

- `score`
- `passed` or `needs_revision`
- `feedback_md`
- `concept_scores`
- `weak_spots`
- `next_action`

Mastery should update only when there is enough evidence from tests, AI review, and follow-up answers.

## V1 Scope

In scope:

- study session model;
- conspect plus task generation;
- mini-project practice tasks;
- JetBrains plugin pairing;
- active task listing in plugin;
- task instructions in plugin;
- manual file or diff submission;
- optional check command output;
- AI evaluation;
- follow-up questions;
- mastery and card updates;
- capsule generation after session completion.

Out of scope:

- browser-based code execution;
- VS Code extension;
- JetBrains multi-product polish beyond first IntelliJ IDEA target;
- full project scaffolding;
- dependency management;
- local agent execution;
- automatic code edits;
- multi-user classroom/team workflows;
- marketplace publication as a release blocker.

## Risks And Mitigations

### Risk: The plugin becomes a second product.

Mitigation: keep the plugin as evidence transport and status display. All learning logic stays in Proof Forge.

### Risk: Local environment issues pollute the learning experience.

Mitigation: v1 accepts evidence even without running commands. Check commands are helpful but optional. AI evaluation should explain when evidence is insufficient.

### Risk: Multi-language support expands scope too early.

Mitigation: the bridge accepts files, diff, command output, and language metadata. Language-specific execution stays in the user environment.

### Risk: AI evaluation is unreliable.

Mitigation: combine deterministic evidence, AI review, and follow-up questions. Store raw evidence for audit and re-evaluation.

### Risk: JetBrains plugin compatibility is broad.

Mitigation: build on the IntelliJ Platform, test IntelliJ IDEA first, then expand to PyCharm, WebStorm, and GoLand based on user demand.

## Success Criteria

V1 succeeds if a user can:

1. start a topic;
2. get a conspect and practice task;
3. solve a mini-project in JetBrains;
4. submit the solution without manual archive upload;
5. receive useful evaluation and follow-up;
6. see progress update in Proof Forge;
7. forge a capsule that includes what they practiced and where they struggled.

The feature should feel like Proof Forge now understands real work done in the user's IDE.
