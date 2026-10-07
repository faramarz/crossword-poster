# fonts/

All fonts are Google Fonts released under the **SIL Open Font License 1.1**. Each family directory carries its own
`OFL.txt` (downloaded from github.com/google/fonts). The static TrueType files are instances of the Google Fonts variable
fonts, so Chromium embeds real TrueType instead of Type 3 glyphs in the PDFs.

| Family | Files here | Used by |
|---|---|---|
| Archivo Narrow | Regular, Medium, Bold | `render` (newspaper, main) |
| Oswald | Bold | `render` (title, headings) |
| Bebas Neue | Regular | `render-classic` style B |
| DM Sans | Regular, Medium, Bold, ExtraBold | `render-classic` style B |
| Playfair Display | fetched on demand | `render-classic` styles A, M |
| Source Serif 4 | fetched on demand | `render-classic` styles A, M |

Playfair Display and Source Serif 4 carry a Reserved Font Name, so they are not redistributed in this repository.
Run `scripts/fetch_fonts.sh` once to download them (and their `OFL.txt`) and create the static instances (needs
`pip install fonttools`). `scripts/fetch_fonts.sh --all` re-downloads every family. Set `CROSSWORD_FONT_DIR` to use a
fonts directory elsewhere.
