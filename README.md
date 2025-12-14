# ruarxive-db

Public database of the archived files in Ruarxive.

## Overview

This repository contains a unified YAML database structure that merges metadata from Airtable (collections, plans, status) with file metadata from SFTP storage. The database is organized as individual YAML files for better version control and maintainability.

## Structure

```
data/
├── airtable/          # Source Airtable JSON exports
├── filelists/         # Source file metadata (compressed)
├── normalized/         # Intermediate normalized JSON data
├── collections/       # Collection YAML files (one per collection)
├── records/           # Record YAML files organized by collection
│   ├── memorial2021/  # Records for memorial2021 collection
│   ├── media2022/     # Records for media2022 collection
│   └── ...            # Other collection subdirectories
├── files/              # File list YAML files (one per record with files)
└── metadata/          # Metadata lookup tables (status, sources, etc.)
```

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

### Generate YAML Database

```bash
python3 scripts/merge_datasets.py
```

This will:
1. Transform Airtable data to normalized structure
2. Match files to records (if filelists are available)
3. Generate YAML files for all entities

### Validate Database

```bash
python3 scripts/validate_yaml.py
```

### Build Datasets

Build datasets in multiple formats (JSONL, Parquet, DuckDB) from the YAML database:

```bash
python3 builder.py build
```

This will generate:
- **JSONL files** (compressed with zstandard): `collections.jsonl.zst`, `records.jsonl.zst`, `resources.jsonl.zst`
- **Parquet files**: `collections.parquet`, `records.parquet`, `resources.parquet`
- **DuckDB database**: `ruarxive.duckdb` with separate tables for collections, records, and resources

Output files are written to `data/datasets/` by default. Use `--output-dir` to specify a different location.

## Documentation

See [docs/YAML_DATABASE.md](docs/YAML_DATABASE.md) for detailed documentation on:
- Database schema
- File formats
- Usage examples
- Querying the database

## Scripts

### Main Scripts

- `builder.py` - Build datasets in multiple formats (JSONL, Parquet, DuckDB) from YAML database
- `scripts/merge_datasets.py` - Main pipeline to merge and generate YAML database
- `scripts/transform_airtable.py` - Transform Airtable JSON to normalized structure
- `scripts/match_files.py` - Match filelists to records
- `scripts/generate_yaml.py` - Generate YAML files from normalized data
- `scripts/validate_yaml.py` - Validate YAML database structure
- `scripts/fetch_airtable.py` - Fetch data from Airtable API
- `collect_files.py` - Collect file metadata from SFTP server

## Data Sources

- **Airtable**: Metadata about collections, archive plans, status, sources, etc.
- **SFTP Storage**: File metadata from archived storage directories

## License

See LICENSE file.
