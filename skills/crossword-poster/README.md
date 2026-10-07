# The crossword-poster skill

This folder is a [Claude skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview): a set of
instructions (`SKILL.md`) that teaches Claude how to guide you through making a crossword poster with the
`crossword-poster` tool. It checks that the tool is installed, helps you clean your clues, asks for a title, size and
style, builds the poster, reviews the result and gets you ready for the print shop.

The skill does not contain the tool itself. Claude installs and runs `crossword-poster` on your computer (see
[docs/AI_AGENTS.md](../../docs/AI_AGENTS.md)). Your clues stay on your computer.

## Claude Code

If you cloned this repository, there is nothing to do. The folder `.claude/skills/crossword-poster` is a link to this
folder, so Claude Code finds the skill when you open the repository.

To use the skill in another project, copy this folder into that project's `.claude/skills/` folder:

```bash
mkdir -p .claude/skills
cp -r path/to/crossword-poster/skills/crossword-poster .claude/skills/
```

To make it available in every project, copy it into your personal skills folder instead:

```bash
mkdir -p ~/.claude/skills
cp -r path/to/crossword-poster/skills/crossword-poster ~/.claude/skills/
```

On Windows the personal folder is `.claude\skills` inside your user folder. Start a new Claude Code session afterwards.
Then ask for a crossword poster in your own words, or name the skill, for example "use the crossword-poster skill to
help me make a poster".

## Claude apps (Claude desktop app and claude.ai)

1. Download `crossword-poster-skill.zip` from the
   [Releases page](https://github.com/faramarz/crossword-poster/releases). It contains one folder called
   `crossword-poster`.
2. In Claude, open Settings and look under Capabilities (or Skills) for the option to add a skill, then upload the zip.
   The menu names change from time to time, so if you cannot find it, search Claude's help for "upload a skill".
3. Make sure the skill is switched on.

A skill gives Claude the know-how. To build the PDF, Claude still needs a place where it can run commands: Claude Code,
or Cowork in the desktop app with a folder that holds your clues. In a plain chat, the skill helps with cleaning up the
clues, and you build the poster on your own computer. See [docs/AI_AGENTS.md](../../docs/AI_AGENTS.md).

## Build the zip yourself

From the root of the repository:

```bash
cd skills
zip -r -X ../crossword-poster-skill.zip crossword-poster
```

The folder `crossword-poster` must be at the top of the zip, with `SKILL.md` directly inside it.

## Changing the skill

Keep `SKILL.md` accurate when the command line changes: every flag it mentions must exist in
`crossword-poster --help` and [docs/CLI.md](../../docs/CLI.md). The `description` in the header is how Claude decides
when to use the skill, so keep it under 1024 characters and say what it is for. Use made-up example clues only.
