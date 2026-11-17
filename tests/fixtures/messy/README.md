# Damaged real papers

Made by `tools/make_messy.py` from the real papers in `../real` (CC BY 4.0,
see `../real/ATTRIBUTION.md`), our LaTeX project, and the real Gemini image in
`../images`. Each damage, and the finding Prarup must report for it:

| File | Damage | Finding |
|---|---|---|
| `svm_messy.docx` | Abstract (the layout table) deleted | META-03 no abstract |
| | Keywords deleted with it | META-04 no keywords |
| | "Figure 2" caption deleted | FIG-01 figure without caption |
| | That figure's image shrunk to 400 px | IMG-01 117 dpi |
| | A Gemini image (signed C2PA manifest) added as a figure | IMG-02 declared AI-generated |
| | Figure 3's image added a second time | IMG-05 duplicate |
| | (already in the real paper) Figure 1's drawing is missing | FIG-03 caption without image |
| `uav_messy.docx` | "Figure 1" caption deleted | FIG-01 |
| | Keywords deleted | META-04 |
| | "[99]" cited in the Introduction (50 references) | REF-02 citation past the references |
| `latex_messy.zip` | A zipped LaTeX project: one caption deleted | FIG-01 |
| | The Gemini image as a figure | IMG-02 |
| | A 240 px copy of a plot | IMG-01 70 dpi, IMG-05 duplicate |
| | The same plot used twice | IMG-05 |
| | (from the project) `\cite{ghost}`, an uncited reference, a missing image | REF-02, REF-03, FIG-03 |
