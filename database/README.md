# Database

The Level 3 database is SQLite, not an external server.

Code entrypoints:

- `database/visual_baseline_store.py` exports the SQLite `BaselineStore`.
- `core/visual_baseline_store.py` contains the implementation used by the scan engine.

Default path:

```text
output/baselines/baselines.db
```

It stores:

- `baselines`: one baseline screenshot record per configured page.
- `baseline_versions`: immutable baseline versions created on each baseline save or refresh.
- `scan_runs`: scan history and report paths.

The actual baseline images are PNG files beside the SQLite database:

```text
output/baselines/{page_id}.png
output/baselines/versions/{page_id}_{scan_id}_{timestamp}.png
```

You can override the database path with:

```env
BASELINE_DB_PATH=output/baselines/baselines.db
```
