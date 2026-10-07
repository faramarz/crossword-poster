# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |
| Older than 1.0 | No |

Security fixes go into the latest 1.x release.

## Reporting a vulnerability

Please report security problems privately. Do not open a public issue.

- Email **gm@faramarz.xyz** with "crossword-poster security" in the subject, or
- Use GitHub's private reporting: go to the repository's **Security** tab and choose **Report a vulnerability**
  ([direct link](https://github.com/faramarz/crossword-poster/security/advisories/new)).

Please include:

- what you found and why it matters,
- the version (`crossword-poster --version`) and your operating system,
- the smallest clues file or command that shows the problem (use made-up clues, not real private ones).

This is a small, volunteer-run project. I aim to acknowledge a report within a week and to tell you what I plan to do about
it. Please give me a reasonable time to fix a problem before you share it publicly. I am happy to credit you in the
release notes if you want.

## What is in scope

crossword-poster is a **local command line tool**. It reads a clues file you choose, runs entirely on your computer and
writes files to a folder you choose. It has no server, accounts or network service, and it does not upload anything.

Things I treat as security problems:

- **Untrusted clue text escaping the page.** Clues, answers, titles and subtitles can come from other people. They are
  printed literally. They reach the layout page either inside an escaped JSON block (so `</script>` and `<!--` cannot
  break out) or through escaped text, and the tests check that markup in a clue shows up as text. A way to run script or
  change the layout through a CSV or a title is in scope.
- **Unsafe file handling:** writing outside the output folder, following a crafted file name, or unsafe handling of a
  crafted CSV or `.xlsx` file.
- **Code execution** from a crafted input file.
- **The supply chain:** a dependency problem that the project can fix (for example by raising a minimum version).

## What is out of scope

- Vulnerabilities in Chromium, Playwright, Python or other dependencies themselves. Please report those upstream. If a fix
  needs a version bump here, tell me and I will do it.
- Problems that need an attacker who already controls your computer or your account.
- Running the tool on files you were told to trust, after changing the code yourself.
- The output of the tool being "wrong" in a non-security way (a layout problem, a clue that does not fit). Use the normal
  [issue tracker](https://github.com/faramarz/crossword-poster/issues/new/choose) for those.

## Good practice for users

- Keep your private clue files out of public places. The repository's `.gitignore` already ignores the `data/` folder and
  any file named `*.private.*`.
- Install the tool from the official repository, and keep Playwright and Chromium up to date.
