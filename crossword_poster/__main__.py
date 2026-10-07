"""``python -m crossword_poster`` runs the same command line as the ``crossword-poster`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
