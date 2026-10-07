# data/

Put your own, private clue CSVs here (for example `data/my_clues.csv`). Everything in this directory except this
README is **gitignored**, as are `out/` and any file named `*.private.*`, so clues, answers and names for a real
project never end up in the repository.

Expected CSV shape (the header row names the columns; `clue`/`clues`/`question` and `answer`/`answers`/`word` are
found automatically, in any letter case; `id` is optional; use `--clue-column` / `--answer-column` for other names):

```
id,clue,answer
1,Capital of France,Paris
2,Large Australian marsupial that hops,Kangaroo
```

`crossword-poster template data/my_clues.csv` writes a starter file. Then build:

```
crossword-poster build --clues data/my_clues.csv --size 24x36 --out out/ \
    --title "My Crossword" --subtitle "Made with love"
```

Keep clue answers out of commit messages, issue text and screenshots as well.
