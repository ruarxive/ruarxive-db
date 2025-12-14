# YAML Database Structure

This document describes the unified YAML database structure for the Ruarxive archive database.

## Overview

The YAML database merges metadata from Airtable (collections, plans, status) with file metadata from SFTP storage into a hierarchical, human-readable structure. Each entity (collection, record, file list) is stored in its own YAML file for better version control and maintainability.

## Directory Structure

```
data/
├── collections/           # One YAML file per collection
│   ├── memorial2021.yaml
│   ├── echomskru2022.yaml
│   └── ...
├── records/              # Records organized by collection subdirectories
│   ├── memorial2021/     # Records for memorial2021 collection
│   │   ├── 1937-memo-ru.yaml
│   │   ├── 1968-memo-ru.yaml
│   │   └── ...
│   ├── artculturemedia_sygma/  # Records for artculturemedia_sygma collection
│   │   ├── syg-ma.yaml
│   │   └── ...
│   └── ...
├── files/                 # File metadata (one file per record with files)
│   ├── recQ8yUy0OvPjvnCB_files.yaml
│   └── ...
└── metadata/             # Lookup tables
    ├── status.yaml
    ├── sources.yaml
    ├── resource_types.yaml
    ├── formats.yaml
    └── reasons.yaml
```

## Schema Definitions

### Collection Schema

Each collection file (`collections/{slug}.yaml`) represents a top-level grouping of archived resources.

**Required Fields:**
- `id`: Airtable record ID (e.g., `recLy818jKOknCZuK`)
- `slug`: Filesystem-safe identifier (e.g., `memorial2021`)
- `name`: Display name (e.g., `Мемориал 2021`)

**Optional Fields:**
- `created`: ISO 8601 timestamp when collection was created
- `description`: Description of the collection
- `collection_type`: Type of collection (e.g., `единовременная`)
- `collection_date`: Date when collection was created (YYYY-MM-DD)
- `reason`: Reason for archiving
- `reason_url`: URL with more information about the reason
- `num_records`: Number of records in this collection
- `records`: List of record summaries (see below)
- `files`: Aggregate file statistics (see below)

**Example:**
```yaml
id: recLy818jKOknCZuK
slug: memorial2021
name: Мемориал 2021
description: Архив Мемориала
collection_type: единовременная
created: 2021-11-22T08:25:09Z
collection_date: 2021-11-22
reason: Требование Генпрокуратуры РФ ликвидировать Международный Мемориал
reason_url: https://www.memo.ru/ru-ru/memorial/departments/intermemorial/news/626
num_records: 67
records:
  - id: recQ8yUy0OvPjvnCB
    name: Название ресурса
    url: https://example.com
    status: собран
files:
  total_count: 1234
  total_size: 1234567890
  directories:
    - webcollect2021
    - webcollect2022
```

### Record Schema

Each record file (`records/{collection_id}/{id}.yaml`) represents an individual archive plan/resource. Records are organized into subdirectories by collection ID for better organization and faster access.

**Required Fields:**
- `id`: Airtable record ID
- `name`: Name of the resource

**Optional Fields:**
- `url`: Original URL of the resource
- `domain`: Extracted domain from URL (for file matching)
- `created`: ISO 8601 timestamp when record was created
- `date`: Archive date (ISO 8601)
- `status`: Current status (e.g., `собран`, `не собран`)
- `status_id`: Reference to status metadata
- `resource_type`: Type of resource (e.g., `официальный сайт организации`)
- `resource_type_id`: Reference to resource_type metadata
- `reason`: Reason for archiving
- `reason_id`: Reference to reason metadata
- `reason_url`: URL with more information
- `strategy`: Archiving strategy (e.g., `стандартная веб архивация`)
- `tools`: List of tools used (e.g., `[wpull]`)
- `format`: Archive format (e.g., `warc`)
- `format_id`: Reference to format metadata
- `collection`: Collection reference (object with `id`, `slug`, `name`)
- `source`: Source organization (object with `id`, `name`)
- `priority`: Priority level (e.g., `высокий`)
- `storage_url`: URL to storage location
- `cloud_url`: URL to cloud storage
- `files`: File information (see below)

**Example:**
```yaml
id: recQ8yUy0OvPjvnCB
name: Название ресурса
url: https://example.com
domain: example.com
created: 2022-03-29T16:16:48Z
date: 2022-04-05T14:22:00Z
status: собран
status_id: reczw1cLd9zjVZJnL
resource_type: официальный сайт организации
resource_type_id: recITNS4632k0mowN
reason: Сохранение культурного наследия
reason_id: recdVNcTUdSUA1SLp
strategy: стандартная веб архивация
tools:
  - wpull
format: warc
format_id: rec4xC693Wnu2ASjB
collection:
  id: recLy818jKOknCZuK
  slug: memorial2021
  name: Мемориал 2021
source:
  id: recVSGsVT2ZPnhEHT
  name: Международный мемориал
files:
  total_count: 45
  total_size: 123456789
  source_directories:
    - webcollect2021
  file_list: files/recQ8yUy0OvPjvnCB_files.yaml
```

### File List Schema

File lists are stored separately for records with many files (`files/{record_id}_files.yaml`).

**Required Fields:**
- `record_id`: Reference to record ID
- `record_name`: Name of the record
- `total_count`: Total number of files
- `total_size`: Total size in bytes

**Optional Fields:**
- `record_url`: Original URL of the resource
- `source_directories`: List of source directories
- `files`: List of file metadata (see below)

**File Metadata Fields:**
- `path`: Full path to file
- `filename`: Filename
- `size`: File size in bytes
- `modified`: Modification timestamp (ISO 8601)
- `permissions`: File permissions (octal string)
- `uid`: User ID
- `gid`: Group ID
- `source_directory`: Source directory name

**Example:**
```yaml
record_id: recQ8yUy0OvPjvnCB
record_name: Название ресурса
record_url: https://example.com
total_count: 45
total_size: 123456789
source_directories:
  - webcollect2021
files:
  - path: /pool2/archive/public/webcollect2021/site/index.html
    filename: index.html
    size: 12345
    modified: 2022-04-05T14:22:00Z
    permissions: "644"
    source_directory: webcollect2021
```

### Metadata Schema

Metadata lookup tables are stored in `metadata/` directory.

**Structure:**
```yaml
items:
  - id: rec4r3omE6WhWzQWm
    name: не собран
    created: 2022-12-28T11:33:41Z
  - id: recAT2fBxxOtHxaZT
    name: собирается
    created: 2022-12-28T11:33:41Z
```

**Available Metadata Files:**
- `status.yaml`: Archive status values
- `sources.yaml`: Source organizations
- `resource_types.yaml`: Resource type classifications
- `formats.yaml`: Archive format types
- `reasons.yaml`: Reasons for archiving

## Usage

### Generating the Database

Run the main merge script to generate the YAML database:

```bash
python3 scripts/merge_datasets.py
```

This script:
1. Transforms Airtable JSON data to normalized structure
2. Matches filelists to records (if available)
3. Generates YAML files for all entities

### Validating the Database

Validate the generated YAML structure:

```bash
python3 scripts/validate_yaml.py
```

This checks:
- Required fields are present
- References between entities are valid
- File counts are consistent

### Building Datasets

Build datasets in multiple formats from the YAML database:

```bash
python3 builder.py build
```

This generates:
- **JSONL files** (compressed with zstandard): Collections, records, and resources as separate compressed JSONL files
- **Parquet files**: Columnar format optimized for analytics, with zstandard compression
- **DuckDB database**: SQL database with separate tables for collections, records, and resources

The builder:
1. Loads all collections and records from YAML files
2. Normalizes the data structures
3. Extracts resources from records into a separate dataset
4. Exports to all three formats

Output is written to `data/datasets/` by default. Use `--output-dir` to specify a different location.

**Example usage:**
```bash
# Build with default output directory
python3 builder.py build

# Build to custom directory
python3 builder.py build --output-dir /path/to/output
```

### Querying the Database

You can use standard YAML tools to query the database:

**Using `yq` (YAML processor):**
```bash
# Find all collections
yq eval '.name' data/collections/*.yaml

# Find records with specific status
yq eval 'select(.status == "собран")' data/records/*.yaml

# Count files in a collection
yq eval '.files.total_count' data/collections/memorial2021.yaml
```

**Using Python:**
```python
import yaml
from pathlib import Path

# Load a collection
with open('data/collections/memorial2021.yaml') as f:
    collection = yaml.safe_load(f)

# List all records
records_dir = Path('data/records')
for record_file in records_dir.glob('*.yaml'):
    with open(record_file) as f:
        record = yaml.safe_load(f)
        print(record['name'])
```

## Migration Notes

- Original JSON files in `data/airtable/` and `data/filelists/` are preserved as source data
- Normalized intermediate data is stored in `data/normalized/`
- The YAML database is generated from normalized data
- Old structure can be deprecated after migration is verified

## Benefits

1. **Human-readable**: YAML is easy to read and edit manually
2. **Version control friendly**: One file per entity enables better git diffs
3. **Scalable**: Large file lists can be split into separate files
4. **Queryable**: Can use tools like `yq` or Python to query
5. **Maintainable**: Clear separation of concerns (collections, records, files, metadata)
6. **Multi-format export**: Built-in support for exporting to JSONL, Parquet, and DuckDB formats for different use cases
