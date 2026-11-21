# Demonstration runtime

Start with the [installation guide](../README.md) or `../START_HERE.txt`. On Windows, use `START_DEMO.cmd`; `CHECK_DEMO.cmd` checks installation prerequisites without starting the website.

The runtime contains the Python service, local browser assets, CSV validator, reference/budget calculations, locked dependency definitions and prepared historical data. It is a selected executable subset of the [full project repository](https://github.com/Graham-Hz/FYP_Game).

The source repository also contains the cleaning pipeline, modelling experiments and research evidence. Those larger development workflows and original raw datasets are not needed to run this demonstration and are not included here.

- [Feature walkthrough](DEMO_GUIDE.md)
- [CSV import specification](CSV_IMPORT_GUIDE.md)
- [Data provenance and limits](../DATA_SOURCES.md)

Imported data versions are written to `data/application/`. The shipped research artifacts remain unchanged. Keep `Dataset/` beside `Program/` for the source-linked cost and fee libraries.

Use **匯入資料** in the left sidebar (`/import`) for confirmed column mapping and partial Steam/Android snapshots. Preview which analyses have enough fields, save a version, then activate it. Market exploration and stricter planning comparison have separate row counts. Original files, mappings and validation records are retained; research partitions are not retrained. The legacy exact-template importer is also retained.
