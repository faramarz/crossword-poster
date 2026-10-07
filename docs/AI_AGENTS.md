# Make your poster with an AI assistant

You do not have to type the commands yourself. An AI assistant that can run commands on your computer can install the
tool, check your clues, build the poster and tell you what to send to the print shop. You stay in charge of the clues,
the title and the look. This page shows how to set that up with the most common assistants, and gives you prompts to copy.

You do not need to be a programmer. If you would rather do it by hand, the [beginner guide](GUIDE.md) covers every step.

**On this page**

- [What an assistant can and cannot do here](#what-an-assistant-can-and-cannot-do-here)
- [Before you start](#before-you-start)
- [Claude Code](#claude-code)
- [Claude desktop app with Cowork](#claude-desktop-app-with-cowork)
- [Claude chat without Cowork](#claude-chat-without-cowork)
- [Add the crossword-poster skill to Claude](#add-the-crossword-poster-skill-to-claude)
- [Other assistants](#other-assistants)
- [The universal prompt](#the-universal-prompt)
- [Privacy](#privacy)
- [If something goes wrong](#if-something-goes-wrong)

---

## What an assistant can and cannot do here

The poster is built by a program on a computer, so the assistant must be able to run that program.

| Kind of assistant | Can it build the PDF? | What it is good for |
|---|---|---|
| **Runs commands on your computer** (Claude Code, Claude's Cowork, Codex, Cursor, GitHub Copilot in agent mode, Gemini CLI) | Yes | Everything: install the tool, clean the clues, build, check the result, explain the warnings. |
| **A plain chat** (the chat window in a browser or an app, with no folder or terminal connected) | No | Collecting, cleaning and de-duplicating clues into the CSV format. You then build the poster yourself, or hand the CSV to an assistant from the first row of this table. |

An assistant is good at the tedious parts: spotting clues typed into the answer box, answers with numbers, duplicates,
clues that are too long, and a first tidy of the wording. It is not a fact checker. It does not know your friend's
nickname or the year of your trip, so you still read every clue and answer yourself. Ask it to point out what looks
wrong and leave the final decisions to you.

What the assistant works from:

- **Your clues file.** A CSV (or Excel `.xlsx`) with a `clue` column and an `answer` column. Ask the assistant to make
  the starter file with `crossword-poster template my_clues.csv` if you have nothing yet.
- **The tool's own checks.** The tool tells the assistant, in plain messages, which rows it skipped and why, which
  answers did not fit, and whether the finished PDFs passed its checks.
- **This repository's instructions.** [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md) are read automatically by
  most coding assistants. For Claude there is also a [skill](../skills/crossword-poster/SKILL.md) that walks through the
  whole job.

## Before you start

You need:

1. **A clues file**, or at least the raw clues (a spreadsheet, a Google Form export, or messages you can paste). The
   [guide](GUIDE.md#2-collect-clues-from-friends-and-family) has a ready-made form and email text for collecting them.
2. **An account with the assistant you choose.** Each one has its own sign-up and pricing. Check the assistant's own
   website.
3. **A working folder** on your computer, such as `crossword` on your Desktop, with your clues file inside. Put your
   clues in this folder and nowhere public.
4. **An internet connection** for the one-time setup. The tool downloads about 300 MB of Chromium, the browser engine
   that prints the poster. After that it works offline.

Two ways to set up the folder. Either works with every assistant on this page:

- **A new folder with your clues file in it** (the simplest). The assistant installs the tool from GitHub for you.
- **A copy of this repository** (`git clone`, shown below). Assistants then read [AGENTS.md](../AGENTS.md)
  automatically, and Claude Code finds the project skill. Keep your clues in the `data/` folder of the copy. Git
  ignores that folder, so your clues cannot be committed by accident.

The tool is not on PyPI. It installs from GitHub, with either of these commands (the assistant knows them, but it helps
to recognise them):

```bash
pipx install git+https://github.com/faramarz/crossword-poster
```

```bash
uv tool install git+https://github.com/faramarz/crossword-poster
```

then, once:

```bash
crossword-poster install-browser
```

---

## Claude Code

Claude Code is Anthropic's coding assistant that runs in a terminal window or inside an editor such as VS Code. It can
run commands and edit files in the folder you open it in. This is the most complete way to use the tool with an
assistant.

**1. Install Claude Code and sign in.** Follow the install steps for your computer in
[Anthropic's Claude Code documentation](https://code.claude.com/docs/en/overview). They change from time to
time, so use that page rather than a copy.

**2. Get this repository and open Claude Code in it.** Open a terminal and run these lines one at a time (you need Git;
the [guide](GUIDE.md#4-install-the-tool) shows how to open a terminal):

```bash
git clone https://github.com/faramarz/crossword-poster
cd crossword-poster
claude
```

Claude Code reads [CLAUDE.md](../CLAUDE.md) (which points to [AGENTS.md](../AGENTS.md)) automatically when it starts in
this folder. It also finds the project skill, [crossword-poster](../skills/crossword-poster/SKILL.md), because
a copy of it ships in `.claude/skills/crossword-poster`. If you would rather not clone, open Claude Code in any folder and add the
skill as described [below](#add-the-crossword-poster-skill-to-claude).

**3. Put your clues file in the `data/` folder** of the copy (for example `data/my_clues.csv`). Claude Code asks your
permission before it runs commands or changes files. Read each request before you approve it.

**4. Check the computer and see the sample.** Paste this into Claude Code:

```text
I want to make a crossword poster with this tool. First check that this computer is ready: run `crossword-poster doctor`.
If the tool or its browser is missing, install it from GitHub (the README quick start has the commands; use pipx or uv)
and run `crossword-poster install-browser`, then `crossword-poster doctor` again. When it says everything is ready, build
the fictional sample with `crossword-poster sample --out my-first-poster` and tell me which files it made and where they
are. Explain each step in plain words. I am not a programmer.
```

**5. Build from your own clues.** Paste this, and fill in the square brackets:

```text
Use the crossword-poster skill. My clues are in data/my_clues.csv. Please check the file first: look for answers and
clues that were typed the wrong way round, duplicates, answers with numbers, clues that are too long, and anything that
gives away its own answer. Show me what you find and ask me before you change any clue or answer; work on a copy and
keep my original file. Then build the poster:
- Title: [Sam's 50th Birthday]
- Subtitle: [Clues from everyone who loves you]
- Size: [24x36] inches
- Style: [grey]
- Put the results in a folder called poster/ next to my clues file.
When it is built, read me the summary in plain words: did every answer fit, how big are the squares and the clue text,
and did all the output checks pass. Tell me which file to send to the print shop. Keep my clues on this computer: do not
upload them anywhere and do not commit them to git.
```

If the skill is not available, the same prompt still works, because Claude Code reads AGENTS.md and the tool prints its
own guidance. You can also use the [universal prompt](#the-universal-prompt).

**6. Look at the result.** Open `poster/poster_24x36_grey_preview.png` to see the poster, and print the
`actual_size_check_24x36.pdf` page at 100% to judge the real size before you order. Then follow the guide for
[printing](GUIDE.md#7-print).

## Claude desktop app with Cowork

In the Claude desktop app, Cowork lets Claude work on files in a folder you choose. It can run commands for you, inside a
sandbox on your computer. This is a good choice if you would rather not use a terminal at all.

**1. Install the Claude desktop app and sign in.** Download it from Anthropic's website. Check Anthropic's help pages
to see whether Cowork is available on your plan.

**2. Make a folder** such as `crossword` on your Desktop and put your clues spreadsheet in it (CSV is best; Excel
`.xlsx` also works if the assistant adds the Excel reader, see below).

**3. Start a Cowork task and choose that folder** when the app asks which folder Claude may use. Look for the folder
choice or the "add a folder" option when you start. Choose only the folder with your clues, not your whole computer.

**4. Paste this prompt:**

```text
I want to make a crossword poster from the clues in my connected folder, using the free tool crossword-poster
(https://github.com/faramarz/crossword-poster). I am not a programmer, so explain each step in plain words.

1. Check whether `crossword-poster` is installed by running `crossword-poster doctor`. If it is not, install it from
   GitHub with `pipx install git+https://github.com/faramarz/crossword-poster` (or, if pipx is not available,
   `uv tool install git+https://github.com/faramarz/crossword-poster`). Then run `crossword-poster install-browser` and
   `crossword-poster doctor` again.
2. If the browser download is blocked in this environment, do not keep retrying. Tell me exactly which commands to run on
   my own computer instead, and wait for me.
3. Look at my clues file. Check for clues and answers typed the wrong way round, duplicates, answers with numbers and
   clues that are too long. Show me what you find and ask before changing anything. Work on a copy.
4. Build the poster with `crossword-poster build --clues [my_clues.csv] --title "[Sam's 50th Birthday]" --subtitle "[Clues from everyone who loves you]" --size 24x36 --style grey --out poster/`
5. Tell me in plain words whether every answer fit, how big the squares and text are, and whether all checks passed.
   Tell me which PDF to send to a print shop.

Keep everything in this folder. Do not upload my clues anywhere.
```

**5. Find your files.** The results are written to the `poster` folder inside the folder you connected, so you can open
them from your normal file browser.

**If the sandbox blocks the download.** Cowork may run with limited network access. If Chromium cannot be downloaded
there, or the install commands fail with a network error, do the one-time setup on your own computer instead, and then
ask Claude to build:

1. Follow the [install steps in the guide](GUIDE.md#4-install-the-tool) for your computer, or the two commands in the
   [README quick start](../README.md#quick-start).
2. Run `crossword-poster doctor`. It should end with `Everything is ready.`
3. Build the poster yourself with the command in the [guide](GUIDE.md#5-build-the-poster), using Claude only for the clue
   clean-up (see the next section).

**Excel files.** The tool reads `.xlsx` only when its Excel reader is installed. The easiest route is to ask Claude to
save a CSV copy of your spreadsheet (CSV UTF-8) and use that.

## Claude chat without Cowork

If you use Claude in a browser or in an app, with no folder connected and no way to run commands, it cannot build the
PDF. It is still very good at the clue clean-up, which is the slowest part of the job.

**1. Remove names before you paste.** If your form collected contributor names or emails, delete those columns first.
Only the clue and the answer are needed.

**2. Paste this prompt**, then paste your list (or attach the exported file) underneath it:

```text
I am making a crossword poster for a special occasion. Below is a list of clues and answers collected from friends and
family. Please turn it into a clean two-column CSV with the headings `clue` and `answer`, and tell me what you found.

Rules:
- The clue is the hint people read. The answer is the word or short phrase that goes in the grid.
- Keep each person's wording. Do not invent new clues, add facts or change names and spellings. Only fix obvious typos
  and tell me about each one.
- Some people put the answer in the clue box and the clue in the answer box. If a row looks swapped (for example the
  "answer" is a sentence or a question and the "clue" is one word), swap it back and list the row.
- Answers must be letters only (spaces, hyphens and apostrophes are fine). If an answer contains a digit, such as 1976 or
  50th, do not drop it: list it so I can decide how to spell it out or change the clue.
- Answers must be 2 to 20 letters once spaces and punctuation are removed. List any that are shorter or longer.
- Remove an answer that appears twice only after you show me both clues and I choose. List near-duplicates too, such as
  Biscuit and Biscuits.
- List clues longer than 20 words, and clues that contain their own answer or another answer from the list.
- List anything that might embarrass or hurt the guest of honour, or contains private details such as an address, a phone
  number, health or money. Do not remove it yourself.

Give me three things: (1) a table of every problem, with the row, what is wrong and your suggestion; (2) the cleaned
list as a CSV in a code block, with the problem rows still in it so I can decide; (3) the count of usable clues.

Here is my list:
[paste your clues here]
```

**3. Decide.** Answer the questions, ask Claude to apply your decisions, and ask for the final CSV again.

**4. Save the CSV.** Copy the CSV from the code block into a plain text file named `my_clues.csv`, or into a spreadsheet and
save as **CSV UTF-8**. If your chat tool offers a file download, use that.

**5. Build the poster.** Either follow the [guide](GUIDE.md#5-build-the-poster) on your own computer, or open the CSV in
Claude Code or Cowork (above) and use the prompts there.

## Add the crossword-poster skill to Claude

A skill is a folder of instructions that Claude loads when a job needs it. The `crossword-poster` skill teaches Claude the
whole workflow in this repository: check the install, clean the clues, ask for your title, size and style, build, review
the warnings, and prepare the print shop hand-off. It also tells Claude to keep your clues private.

**In Claude Code.** If you cloned this repository there is nothing to do: `.claude/skills/crossword-poster` holds a copy of
the skill. To use it in another folder, copy the skill folder into `.claude/skills/` in that folder, or into
`.claude/skills/` inside your home folder to have it everywhere. The exact commands are in
[skills/crossword-poster/README.md](../skills/crossword-poster/README.md).

**In the Claude apps** (the desktop app and claude.ai):

1. Download `crossword-poster-skill.zip` from the
   [Releases page](https://github.com/faramarz/crossword-poster/releases). If the latest release does not list it yet,
   the [skill README](../skills/crossword-poster/README.md#build-the-zip-yourself) shows how to make the zip.
2. In Claude, open Settings and look under Capabilities (or Skills) for the option to add a skill. Upload the zip there.
   Menus change from time to time, so if you cannot find it, search Claude's help for "upload a skill".
3. Turn the skill on, then ask for a crossword poster in your own words.

In a plain chat the skill helps with the clue clean-up and with planning. To build the PDF Claude still needs Claude Code
or Cowork, or you build on your own computer.

---

## Other assistants

These all run commands on your computer, so the same ideas apply. Each of them has its own install and sign-in steps on
its maker's website, which change over time, so the steps below only cover what is specific to this tool. Most of them
read [AGENTS.md](../AGENTS.md) in the folder automatically. If yours does not, the universal prompt asks it to read the
file.

For all of them, first get the folder ready, then paste the [universal prompt](#the-universal-prompt):

```bash
git clone https://github.com/faramarz/crossword-poster
cd crossword-poster
```

Put your clues file in the `data/` folder of the copy.

**OpenAI Codex (and ChatGPT).** Use Codex, the coding agent, in a terminal or in your editor, so that it can run commands
in your folder. Open it in the `crossword-poster` folder, check that it asks permission before running commands, and
paste the universal prompt. An ordinary ChatGPT conversation cannot build the poster, but you can use it for the clue
clean-up with the [chat prompt above](#claude-chat-without-cowork).

**Cursor.** Open the `crossword-poster` folder in Cursor, open the chat panel, choose Agent mode, and paste the universal
prompt. Approve the terminal commands when it asks.

**GitHub Copilot (agent mode).** In VS Code, open the `crossword-poster` folder, open Copilot Chat, switch it to Agent
mode, and paste the universal prompt. Use agent mode in your editor. Chat on github.com cannot run commands on your
computer, and sending your clues to a repository or issue on GitHub would make them visible to others.

**Gemini CLI.** In a terminal, go into the `crossword-poster` folder, start `gemini`, and paste the universal prompt.
Gemini CLI looks for a `GEMINI.md` file by default, so the prompt tells it to read AGENTS.md.

**Any other agent that reads AGENTS.md.** Open the folder, make sure the agent may run shell commands, and paste the
universal prompt.

## The universal prompt

This prompt works in any assistant that can run shell commands. Fill in the square brackets before you paste it.

```text
I want to make a printable crossword poster from a list of clues, using the free command line tool
crossword-poster (https://github.com/faramarz/crossword-poster). I am not a programmer. Please explain what you are doing
in plain words, one step at a time, and ask me before you do anything beyond installing this tool and working with my
clues file.

If this folder has an AGENTS.md or README.md, read the part about making a poster first.

My clues file: [data/my_clues.csv]
Poster title: [Sam's 50th Birthday]
Subtitle (optional): [Clues from everyone who loves you]
Size in inches: [24x36]   (18x24 is smaller and cheaper, 36x48 is for a crowd)
Style: [grey]   (grey saves ink and is easy to write on, black is bold, icons adds a cake and a party hat)

Please do this:
1. Run `crossword-poster doctor`. If the command is not found, install the tool from GitHub (it is not on PyPI) with
   `pipx install git+https://github.com/faramarz/crossword-poster`, or with
   `uv tool install git+https://github.com/faramarz/crossword-poster` if pipx is not available. Then run
   `crossword-poster install-browser` (on Linux add `--with-deps`) and `crossword-poster doctor` again. If a download is
   blocked, stop, and tell me the exact commands to run myself.
2. Check my clues file for: the headings `clue` and `answer`; clues and answers typed the wrong way round; answers with
   numbers; answers shorter than 2 or longer than 20 letters; duplicates and near-duplicates; clues that are too long
   (aim for 12 words or fewer) or that contain their own answer; anything that might embarrass the guest of honour.
   `crossword-poster pool --clues [my_clues.csv] --out pool_check.csv` lists skipped rows and warnings without needing
   the browser. Show me every problem and ask before you change a clue or an answer. Work on a copy and keep my original.
3. Build the poster with one command: `crossword-poster build --clues [my_clues.csv] --title "[Sam's 50th Birthday]" --subtitle "[Clues from everyone who loves you]" --size 24x36 --style grey --out poster/`
4. Tell me in plain words: did every answer fit, how big are the squares (in inches) and the clue text (in points), did
   all the output checks pass, and what warnings there were. If an answer did not fit, offer options such as another
   `--seed`, a bigger size or a changed answer.
5. Tell me where the files are, which PDF to send to a print shop (the one ending in `_bleed.pdf`), and remind me to
   print the actual-size check page at 100% before I order.

Privacy: my clues are personal and may be for a surprise. Keep them on this computer. Do not upload them, post them,
paste them into an issue or a web form, or commit them to git. If you need to report a problem, use made-up examples.
```

---

## Privacy

Clues are personal, and the poster is often a surprise. Keep two things apart:

- **The tool is offline.** `crossword-poster` reads your CSV, builds the PDFs on your computer and uploads nothing. The
  only network use is the downloads you start: the tool itself from GitHub, and Chromium. The `crossword-poster feedback`
  command only prints links and never reads your clues.
- **An assistant is a different matter.** A chat or agent service receives whatever it reads, which includes your clues if
  you paste them in or let it open the file. That is covered by that service's own privacy terms. Check the settings of
  the service you use, and think about who might see the conversation or the screen if the poster is a surprise. To share
  less, give the assistant only the `clue` and `answer` columns and not the names or emails of the people who sent them.

Good habits:

- Tell the assistant, in your first message, not to upload, post or commit your clue file. The prompts on this page say so.
- If you work in a copy of this repository, keep your clues in `data/`, which Git ignores. Never run `git add` on them, and
  never push your copy anywhere public.
- Never paste real clues or names into a GitHub issue, discussion or feedback form. Made-up examples that show the same
  problem are enough. If you want to share how it went, `crossword-poster feedback` prints the links.
- The files in the poster folder (the PDFs, `clues_and_answers.csv`) contain your clues. Treat them the same way.

## If something goes wrong

Ask the assistant to run `crossword-poster doctor` and read you the result. It checks Python, the fonts and Chromium, and
prints a `Fix:` line under anything that is wrong.

| What you see | What it means | What to do |
|---|---|---|
| Exit code `3`, or a message that Chromium "was not found or could not start" | The browser that prints the poster is missing or cannot start. | Run `crossword-poster install-browser` (on Linux `crossword-poster install-browser --with-deps`, which uses `sudo`), then `crossword-poster doctor`. |
| The Chromium download fails or is blocked | The assistant's environment or your network blocks the download. | Run the install commands on your own computer ([install steps](GUIDE.md#4-install-the-tool)). |
| `command not found` for `crossword-poster` right after installing | The folder the installer uses is not on the PATH yet. | Run `pipx ensurepath` (or `uv tool update-shell`), then open a new terminal. If the assistant started before the install, restart it. |
| Exit code `2` and an `Error:` line with `How to fix:` | A problem with your input or options, such as a missing `clue` column. | Follow the `How to fix:` line. The assistant can rename the headings or pass `--clue-column` and `--answer-column`. |
| Exit code `1` | The poster was built but needs attention: an output check failed, or `--require-all` was used and an answer did not fit. | Read the lines above the summary. Open the PDFs before printing. |
| "Some of my answers did not fit" | An answer cannot cross any other, or the grid search ran out of room. | Try `--seed 2`, `--attempts 3000`, a bigger `--size`, or change the answer. |
| Squares or text look too small | Many clues on a small poster. | Choose a bigger size or fewer clues; see [the size table](GUIDE.md#how-many-clues-fit-each-poster-size). |
| An accented name looks like `ZoÃ«` | The file was saved in an old encoding. | Save it as **CSV UTF-8**. |

**Where the files are.** Everything the build makes is in the folder named by `--out` (for example `poster/`). The file to
print is `poster_<size>_<style>_bleed.pdf`. The numbered list of clues and answers for proofreading is
`clues_and_answers.csv`, the picture is `poster_<size>_<style>_preview.png`, and the working files are in `details/`. The
[README](../README.md#what-you-get) and the [CLI reference](CLI.md#the-files-build-writes) describe each file. If
you do not give `--out`, the build writes to a folder called `out` (and `sample` to `sample-poster`) in the folder where
the command ran.

**Still stuck?** See [Troubleshooting](TROUBLESHOOTING.md), run `crossword-poster feedback` to get the links for asking
for help, or open an issue with made-up examples. Do not paste your real clues.
