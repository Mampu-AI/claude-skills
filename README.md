# Mampu AI Claude Code skills

Team skills for Claude Code, distributed as a plugin marketplace.

This marketplace is registered for the whole Claude organization through managed settings (`extraKnownMarketplaces`), so members get the skills automatically.

## Skills

| Skill | Use it for |
|---|---|
| `work-loop` | The AI-native work loop: every work-shaped prompt finds or creates the team task, reads the matching internal records and help pages, opens with the four-line status block and closes the task out with a debrief. Driven by the plugin's hooks and the Mampu Tech Team MCP tools |

## Work loop setup (one time)

**Easiest:** open Claude Code and say *"connect me to the company Lark and docs"*. Claude runs the
sign-in for you (one browser tab), checks it, and gives you the two-minute brief.

By hand: sign in with Lark from the computer you work on. One login per computer and OS user; it lasts while
you keep using it and lapses after a month idle.

```
sh ~/.claude/plugins/cache/mampu/mampu-skills/<version>/scripts/login.sh
```

A browser tab opens on Lark; after you approve, the terminal says "Signed in as …" and the login is in
your keychain. `scripts/login.sh --logout` revokes it. If no browser can open on that machine, the
printed URL works from anywhere and the page shows a one-time token for `scripts/save-token.sh`.

The Lark sign-in is the only login the plugin sends. An old Sapot staff token (`SAPOT_STAFF_TOKEN`, used by the
flows plugin) is ignored here; the server refuses it.

## Adding a skill

1. Add `plugins/mampu-skills/skills/<skill-name>/SKILL.md` (plus any files it links to).
2. Run `claude plugin validate .`, then merge to `main`.

Every merge to `main` is a release: the manifest has no `version` field on purpose, so machines track the
commits and nothing has to be bumped. Claude Code hands out a new copy only when the version changes, and a
forgotten bump would reach nobody and say nothing. `validate` warns "No version specified"; leave it that way.
Teammates pick the new commit up in the background and load it at their next Claude Code start.

Never put hosts, credentials, account IDs, or customer data in a skill.

## Manual install (if not provisioned)

```
/plugin marketplace add Mampu-AI/claude-skills
/plugin install mampu-skills@mampu
```
