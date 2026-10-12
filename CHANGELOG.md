# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Website export (`site_export.py`, `builder.py site`)**: builds `data/datasets/site/summary.json` and `resources.json` for ruarxive.org from the storage file lists. Each top-level storage folder is taken from the newest listing that contains it (SFTP snapshot or a copy of `allarchives.csv`); snapshot duplicates are removed; collection names come from the catalog. Schema in `docs/SITE_EXPORT.md`. `site_export.py --check` validates an existing export without the source file lists.
- **Workflow `site-export.yml`**: validates `data/datasets/site/` on pushes and pull requests and notifies the website repository via `repository_dispatch` (needs the `SITE_DISPATCH_TOKEN` secret).
- **Dataset Builder (`builder.py`)**: New script to build datasets in multiple formats from the YAML database
  - Export to compressed JSONL format (using zstandard compression)
  - Export to Parquet format (using zstandard compression)
  - Export to DuckDB database with separate tables for collections, records, and resources
  - Supports normalization of collections, records, and resources data
  - Extracts resources from records into a separate dataset
- **Requirements file (`requirements.txt`)**: Added dependency management file with all required packages:
  - `paramiko>=3.0.0` - SFTP client for file collection
  - `pyyaml>=6.0` - YAML parsing and generation
  - `zstandard>=0.21.0` - Compression for JSONL exports
  - `duckdb>=0.9.0` - Database export functionality
  - `polars>=0.19.0` - Data processing for Parquet export (with pandas fallback)
  - `requests>=2.28.0` - HTTP client for API interactions
  - `beautifulsoup4>=4.11.0` - HTML parsing utilities
- **Documentation (`docs/YAML_DATABASE.md`)**: Comprehensive documentation covering:
  - Database schema definitions for collections, records, files, and metadata
  - Directory structure
  - Usage examples with `yq` and Python
  - Querying patterns and best practices

### Changed

- **README.md**: Significantly expanded with:
  - Detailed project overview
  - Directory structure documentation
  - Quick start guide with prerequisites
  - Instructions for generating and validating the database
  - Documentation links
  - Complete script listing
  - Data sources information

### Documentation

- Added comprehensive YAML database documentation
- Updated README with build instructions for datasets
- Documented all export formats and their use cases
