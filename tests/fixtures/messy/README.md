# Damaged real papers

The Word fixtures are modified copies of the papers in [real](../real/ATTRIBUTION.md).
The LaTeX fixture is based on the [sample LaTeX project](../latex_project/main.tex).

| File | Damage | Finding |
|---|---|---|
| `svm_messy.docx` | Abstract (the layout table) deleted | META-03 no abstract |
| | Keywords deleted with it | META-04 no keywords |
| | "Figure 2" caption deleted | FIG-01 figure without caption |
| | That figure's image shrunk to 400 px | IMG-01 117 dpi |
| | Figure 3's image added a second time | IMG-05 duplicate |
| | (already in the real paper) Figure 1's drawing is missing | FIG-03 caption without image |
| `uav_messy.docx` | "Figure 1" caption deleted | FIG-01 |
| | Keywords deleted | META-04 |
| | "[99]" cited in the Introduction (50 references) | REF-02 citation past the references |
| `latex_messy.zip` | A zipped LaTeX project: one caption deleted | FIG-01 |
| | A 240 px copy of a plot | IMG-01 70 dpi, IMG-05 duplicate |
| | The same plot used twice | IMG-05 |
| | (from the project) `\cite{ghost}`, an uncited reference, a missing image | REF-02, REF-03, FIG-03 |
