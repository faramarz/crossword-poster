# Bundled fonts

Both families come from Google Fonts and are released under the **SIL Open Font License 1.1**. Each family folder
carries its own `OFL.txt`. The files are shipped inside the Python package (`crossword_poster/fonts/`) and are
embedded into the generated HTML, so nothing needs to be installed on the computer and no path needs configuring.

| Family | Files | Used for |
|---|---|---|
| Archivo Narrow | Regular, Medium, Bold | clue text, grid numbers and letters, byline |
| Oswald | Bold | title and the ACROSS / DOWN headings |

The static TrueType files are instances of the Google Fonts variable fonts (so Chromium embeds real TrueType outlines
in the PDFs instead of Type 3 glyphs). They were taken from <https://github.com/google/fonts> (`ofl/archivonarrow`,
`ofl/oswald`). See `THIRD_PARTY_LICENSES.md` in the repository root for the full licence summary.

To add a font, put the `.ttf` and the family's `OFL.txt` in a new folder here, list it in `BUNDLED_FONTS` in
`crossword_poster/common.py`, and add a `font_face(...)` line to `font_faces()` in `crossword_poster/render_news.py`.
