# Research archive

This directory contains the durable research record for SchedResearch.

```text
research/
├── analysis/       Cross-round audits, problem definitions, and design-space notes
├── literature/     Prior-art registry, framework notes, and source records
├── r1-base/        Round 1 research material
├── r2-ooo-npu/     Round 2 NPU OOO/dataflow exploration
└── research_progress.md
```

Executable experiment implementations remain in the top-level `r3/`–`r11/`
directories so their existing module imports and reproduction commands remain
stable. Generated traces and large result payloads remain local according to
the repository `.gitignore`; compact reviewed summaries stay versioned.

The top-level `analysis/`, `literature/`, `r1-base/`, `r2-ooo-npu/`, and
`research_progress.md` entries are compatibility links for existing scripts
and historical documents. New documents should use the canonical `research/`
paths.
