# data/

Put your own, private clue CSVs here (for example `data/my_clues.csv`). Everything in this directory except this
README is **gitignored**, as are `out/` and any file named `*.private.*`, so clues, answers and names for a real
project never end up in the repository.

Expected CSV shape (column names are configurable with `--clue-column`, `--answer-column`, `--id-column`):

```
id,clue,answer
1,Capital of France,Paris
2,Large Australian marsupial that hops,Kangaroo
```

Then build:

```
python -m crossword_poster build --clues data/my_clues.csv --size 24x36 --style grey --out out/ \
    --title "My Crossword" --byline "Made with love"
```

Keep clue answers out of commit messages, issue text and screenshots as well.
