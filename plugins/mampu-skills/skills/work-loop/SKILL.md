---
name: work-loop
description: >-
  Run the Mampu AI work loop on any work-shaped request — a bug to fix, a feature to build, a doc to write, a client ask to handle, an investigation, a PR to ship, a deploy. Finds or creates the team task, reads the matching internal records and help pages, opens the reply with the four-line status block, and closes the task out with a debrief. Not for a plain question or a read-only look.
---

# Work loop

The tools come with this plugin's `mampu-tech-team` server: `team_work_guide`, `team_tasks_open`, `team_task_start`, `team_task_milestone`, `team_task_finish`, `internal_doc_search`, `internal_doc_get`, `internal_doc_save`. The rules live on the server: **fetch `team_work_guide` section `loop` before the first `team_task_start` of a session** and follow it; fetch `status-block`, `records` or `public-docs` when you need them. The hooks tell you the candidates for each prompt; you decide.

## The three calls

1. **`team_task_start`** — at the first prompt that is work. Pass the `task_guid` the prompt context offered, or `create: {title, description}` when nothing matches. Never ask the person whether to start a task: start it and say so in the block.
2. **`team_task_milestone`** — when a PR is opened or merged, or a promote runs (`kind`: pr_opened, pr_merged, promoted; the URL when known).
3. **`team_task_finish`** — before your final reply: `state` done, doing, waiting or blocked; the one-line summary; `debrief` {how, pitfalls, findings}; `changed_paths`; `records` to write or update; `help_pages_checked` with a verdict per page — `unchanged`, `needs_update`, or `missing` with `suggested_title`, `section` and `why_public` (section `public-docs` says what is public); `pr_url` when a PR exists. A flagged page makes the server file one docs request on the help-doc repo; if you can capture real screenshots, also write the page there with that repo's own `help-doc-writing` skill and open a draft PR. Never ask the person to finish the task. **Done** once the work is live and checked: small leftovers (a docs offer, a cleanup, watching the first live case) go in the summary and do not keep the task open. **Waiting** = it waits on the owner or a client; the summary says who and for what. **Doing** = someone is still working on it.

## The status block

Open the reply that starts work with these four lines, and close out with them again. Fixed vocabulary: found / not found / created / updated / unchanged / done / doing / waiting / blocked. The server renders the lines (`block_line`, `block`); print them, never skip them, even when all four are none.

```
Task:      <title> — found, open → marked doing | not found → created "<title>", doing | <title> — done, completed | … doing, note left | … waiting: <who, for what> | … blocked: <why>
Records:   <slug> — found, reading it | none match → will write one at close-out | <slug> — updated | <slug> — created | <slug> — unchanged
Help page: <title> — found, will check after the change | none mention <topic> | <title> — checked, no change needed | <title> — needs update, flagged | <title> — missing, page proposed | …; docs request #<n>
Client:    none on this task
```

## Stale tasks

Once a day the session start lists your stale tasks (shipped but still open or never noted, after three hours; or untouched for a day, three days for waiting). Before other work, show the person that numbered list and ask in one line which are done, waiting (on whom), blocked or still doing, then call `team_task_finish` for each from the answer. Never close a stale task without the owner's word.

## Not that one?

When the person says the task is wrong, call `team_task_start` again with the right `task_guid` (or `create`); the server reverts the earlier one. Print the block again.

## Rules

- No code detail in anything the loop logs. Task titles, summaries, milestone notes, debriefs and records describe the outcome and the procedure in product terms: the screen, the setting, the behaviour, the command a person types. Never source file paths, function, class, module or table names, code or SQL snippets, config keys. The product is protected intellectual property, and the task list and the records reach people who may not read its code. The server refuses a record or a close-out that carries code detail; rewrite and call again.
- Never ask for, accept, print or store the person's access token. If one is pasted, tell them to reset it in their Sapot profile and re-save it with the plugin's `save-token.sh`.
- A tool refusal ("Missing Sapot credentials", "Not allowed", "switched off") means stop and tell the person to check their plugin setup with their Mampu admin; never work around it.
