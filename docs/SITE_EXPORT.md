# Website export

`site_export.py` builds the data shown on [ruarxive.org](https://ruarxive.org): archive statistics on the homepage and the index behind the search "Is the site in the archive?". The website copies these files as is (`npm run data:archive` in [ruarxive.github.io](https://github.com/ruarxive/ruarxive.github.io)).

```bash
python3 site_export.py          # or: python3 builder.py site
```

Requires `pyyaml` and `zstandard`. Output:

| File | Contents |
|---|---|
| `data/datasets/site/summary.json` | Aggregate statistics: totals, sources, volume by year, collections, formats |
| `data/datasets/site/resources.json` | Per-resource index for the website search |

Both files are committed, so the website can fetch them from `https://raw.githubusercontent.com/ruarxive/ruarxive-db/main/data/datasets/site/`.

## Sources

The export reads every storage file list in `data/filelists/` (the folder is not committed):

- `files_YYYYMMDD_HHMMSS.jsonl.zst` — SFTP snapshots made by `dev/scripts/collect_files.py`;
- `allarchives_YYYYMMDD.csv.zst` — copies of the registry [allarchives.csv](https://cdn.ruarxive.org/public/allarchives.csv).

For every top-level storage folder the **newest listing that contains it** is used. A partial snapshot therefore replaces only the folders it covers; other folders keep their figures from older listings. Folders listed in `data/reference/dirlist.txt` but absent from every listing are reported in `unknownDirs`: their volume is unknown and not counted.

The snapshot collector lists a file once per ancestor folder, so snapshot rows are deduplicated by `path`.

Collection names come from `data/collections/*.yaml`, the catalog size from `data/records/**/*.yaml`.

### Collection and resource of a file

Snapshots contain only paths, so the collection and resource are derived from the path relative to `/pool2/archive/public/`, following the conventions of `allarchives.csv`:

| Path | Collection | Resource |
|---|---|---|
| `<top>/<file>` | `<top>` | file name without the last extension |
| `<top>/<a>/<file>` | `<a>` | file name without the last extension |
| `<top>/<a>/<b>/...` | `<a>` | `<b>` without a crawl suffix `-YYYY-MM-DD-<8 hex>` |

Registry rows keep their own `collection` and `domain`; an empty `domain` is derived from the path the same way (for `dataportals/<portal>/<date>/` the collection code, which is the portal domain, is used).

## Updating

1. Put a new listing into `data/filelists/` — a fresh SFTP snapshot or a new copy of `allarchives.csv` named `allarchives_YYYYMMDD.csv.zst`.
2. Run `python3 site_export.py` and check the log: which folders were taken from which listing, and which have no listing.
3. Commit and push `data/datasets/site/` to `main`.

The rest is automatic:

1. `.github/workflows/site-export.yml` validates the export (`python3 site_export.py --check`: schema version, required fields, totals consistent across sources, collections, years and formats) and sends `repository_dispatch` (`ruarxive-db-updated`, with the commit SHA) to `ruarxive/ruarxive.github.io`.
2. The website workflow `sync-archive-data.yml` fetches the export of that commit, commits the changed data files and starts the deployment.

The same check runs on pull requests that touch the export. Without automation, run `npm run data:archive -- --remote` in the website repository (or `--db ../ruarxive-db` for a local clone) and commit the result.

### One-time setup

- In ruarxive-db, add the secret `SITE_DISPATCH_TOKEN`: a fine-grained personal access token with access to `ruarxive/ruarxive.github.io` and the repository permission **Contents: Read and write** (required for `repository_dispatch`).
- In ruarxive.github.io, the sync workflow pushes to `main` with `GITHUB_TOKEN` and starts `deploy.yml`. This works while workflows may write (Settings → Actions → General → Workflow permissions) and `main` is not protected; if `main` gets branch protection, allow GitHub Actions to push or change the workflow to open a pull request.

## Schema (`schemaVersion: 1`)

Breaking changes increase `schemaVersion`; the website refuses unknown versions.

### summary.json

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-12",
  "sources": [
    {
      "kind": "snapshot",
      "file": "files_20251213_174144.jsonl.zst",
      "url": "https://github.com/ruarxive/ruarxive-db",
      "date": "2025-12-13",
      "dirs": ["datacollect", "webcollect2017"],
      "files": 62639,
      "bytes": 8022580225775,
      "skippedRows": 0
    }
  ],
  "unknownDirs": ["webcollect2024"],
  "catalog": { "url": "https://github.com/ruarxive/ruarxive-db", "collections": 88, "records": 2641, "uncatalogued": 108 },
  "totals": { "bytes": 13940464714244, "files": 88598, "domains": 3322, "collections": 182 },
  "byYear": [{ "year": "2017", "bytes": 6038031434063, "files": 28683 }],
  "collections": [
    { "name": "gov", "title": "Государственные сайты", "bytes": 2559466445839, "files": 7154, "domains": 196, "dir": "" }
  ],
  "formats": [{ "key": "warc", "label": "WARC", "bytes": 10615361474541 }]
}
```

- `sources` — listings that contributed at least one folder, newest first. `kind` is `snapshot` or `registry`; `url` is the public location of the listing (the repository for snapshots, since `data/filelists/` is not committed); `dirs` are the top-level folders taken from this listing; `skippedRows` are malformed rows ignored.
- `catalog.uncatalogued` — collections present in storage but missing from `data/collections/`.
- `totals.domains` — number of distinct resources (domains or other resource names from paths).
- `byYear` — by the file modification date in storage, which is not always the capture date.
- `collections` — all collections, largest first. `title` is `null` for uncatalogued collections. `dir` is the common folder of the collection under `https://cdn.ruarxive.org/public/`, or `""` when its files are spread across folders.
- `formats` — volume by file type: `warc`, `db`, `index` (CDX), `packed` (7z, zip, xz…), `log`, `other`.

### resources.json

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-12",
  "publicPrefix": "https://cdn.ruarxive.org/public/",
  "collectionNames": { "deathwatch": "Мониторинг закрытия сайтов" },
  "domains": [
    ["sova-center.ru", [["deathwatch", "webcollect2023/deathwatch/sova-center.ru/", 6, 1692295556228, "2023-09-01", "2023-09-02"]]]
  ]
}
```

Each entry of `domains` is `[resource, [[collection, dir, files, bytes, firstDate, lastDate], ...]]`, collections sorted by volume. `dir` is relative to `publicPrefix` (`""` when there is no common folder); dates are file modification dates.
