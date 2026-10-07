# Third-party licences

crossword-poster itself is released under the [MIT licence](LICENSE). This page lists everything it depends on or
ships, with the licence of each. No Python package it depends on is itself GPL, AGPL or LGPL licensed.

Binary wheels of some libraries (for example Pillow) bundle shared C libraries under their own licences, some
of them copyleft (for example LGPL-2.1+ or GPL-3.0+ with the GCC runtime exception). Those wheels are installed from PyPI
onto your computer; they are not distributed in this repository or in the crossword-poster package, so they place no
obligation on this project or on the posters you make. Read each library's own licence file if you redistribute an
environment that contains them.

The previous PDF library, PyMuPDF (AGPL-3.0 / commercial), is **not** used any more: PDFs are inspected with `pypdf`
and rasterised with `pypdfium2`. NumPy is no longer a dependency either.

## Runtime dependencies (installed by `pip install crossword-poster`)

Checked with `pip-licenses` on a clean Python 3.13 environment (see `scripts/check_licenses.sh`).

| Package | Version checked | Licence | Used for |
|---|---|---|---|
| [playwright](https://github.com/microsoft/playwright-python) | 1.63.0 | Apache-2.0 | drives headless Chromium to lay out and print the poster |
| [greenlet](https://github.com/python-greenlet/greenlet) (via playwright) | 3.5.6 | MIT AND PSF-2.0 | Playwright's synchronous API |
| [pyee](https://github.com/jfhbrook/pyee) (via playwright) | 13.0.1 | MIT | Playwright's event emitter |
| [typing_extensions](https://github.com/python/typing_extensions) (via pyee) | 4.16.0 | PSF-2.0 | typing backports |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.19.0 | BSD-3-Clause | PDF page sizes, fonts, vector colours, building the actual-size check page |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.14.0 | BSD-3-Clause or Apache-2.0 (bundled PDFium: BSD-3-Clause / Apache-2.0, plus the permissive licences of its own dependencies such as FreeType, ICU, lcms, abseil) | PNG previews, text extraction, rasterised checks |
| [Pillow](https://python-pillow.github.io) | 12.3.0 | MIT-CMU (HPND) | reading rasterised pages, writing PNGs, crop montages and pixel checks |

## Optional and development-only

Not installed by default and never redistributed with the package.

| Package | Licence | When |
|---|---|---|
| [openpyxl](https://openpyxl.readthedocs.io), et_xmlfile | MIT | reading `.xlsx` clue files (`pip install "crossword-poster[xlsx]"`) |
| [defusedxml](https://github.com/tiran/defusedxml) | PSF-2.0 | makes openpyxl refuse malicious XML (installed with the `xlsx` extra) |
| [pytest](https://pytest.org) | MIT | tests (`[dev]`) |
| [ruff](https://github.com/astral-sh/ruff) | MIT | lint and format (`[dev]`) |
| [build](https://github.com/pypa/build) | MIT | building the wheel (`[dev]`) |
| [PyYAML](https://pyyaml.org) | MIT | checking the CI workflow files in the tests (`[dev]`) |

## Browser (downloaded separately, not part of this package)

The poster is printed by Chromium, which you install yourself with `python -m playwright install chromium`
(or point `CROSSWORD_POSTER_CHROMIUM` at an existing Chrome/Chromium). Chromium is distributed under its own
BSD-style and other open-source licences; see <https://www.chromium.org/chromium-os/licenses/>. Playwright's
installer also fetches a Node.js driver (MIT) that carries its own notices inside the Playwright wheel.

## Bundled fonts

Both families are from [Google Fonts](https://github.com/google/fonts) under the **SIL Open Font License 1.1**
(neither declares a Reserved Font Name). The licence texts ship next to the fonts in
`crossword_poster/fonts/<Family>/OFL.txt`. The static `.ttf` files are instances of the variable fonts, so that
Chromium embeds real TrueType outlines in the PDFs. Fonts embedded in a PDF you make are yours to print and share;
the OFL does not restrict documents created with the fonts.

| Family | Files | Copyright |
|---|---|---|
| Archivo Narrow | Regular, Medium, Bold | Copyright 2019 The Archivo Narrow Project Authors (<https://github.com/Omnibus-Type/ArchivoNarrow>) |
| Oswald | Bold | Copyright 2016 The Oswald Project Authors (<https://github.com/googlefonts/OswaldFont>) |

## Keeping this file accurate

Run `scripts/check_licenses.sh` after changing dependencies; it installs the package into a throw-away environment
and prints the licence of every installed distribution. A Python dependency that is GPL / AGPL / LGPL must not be added.
The script only sees package-level metadata, not the shared libraries inside binary wheels (see the note at the top).
