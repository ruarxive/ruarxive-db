#!/usr/bin/env python3
"""
Build datasets from collections and records.

Generates datasets in multiple formats:
- JSONL (compressed with zstandard)
- Parquet
- DuckDB database
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    print("Warning: zstandard not available. JSONL compression will be disabled.")

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False
    try:
        import pandas as pd
        HAS_PANDAS = True
    except ImportError:
        HAS_PANDAS = False
        print("Error: polars or pandas is required. Install with: pip install polars")
        sys.exit(1)

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    print("Error: duckdb is required. Install with: pip install duckdb")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_yaml_file(file_path: Path) -> Optional[Dict]:
    """Load YAML file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Error loading {file_path}: {e}")
        return None


def load_collections(project_root: Path) -> List[Dict]:
    """Load all collections from YAML files."""
    collections_dir = project_root / 'data' / 'collections'
    collections = []
    
    if not collections_dir.exists():
        logger.warning(f"Collections directory not found: {collections_dir}")
        return collections
    
    logger.info(f"Loading collections from {collections_dir}...")
    collection_files = list(collections_dir.glob('*.yaml'))
    logger.info(f"Found {len(collection_files)} collection files")
    
    for collection_file in sorted(collection_files):
        collection_data = load_yaml_file(collection_file)
        if collection_data and 'id' in collection_data:
            collections.append(collection_data)
        else:
            logger.warning(f"Skipping invalid collection file: {collection_file}")
    
    logger.info(f"Loaded {len(collections)} collections")
    return collections


def load_records(project_root: Path) -> List[Dict]:
    """Load all records from YAML files recursively."""
    records_dir = project_root / 'data' / 'records'
    records = []
    
    if not records_dir.exists():
        logger.warning(f"Records directory not found: {records_dir}")
        return records
    
    logger.info(f"Loading records from {records_dir}...")
    record_files = list(records_dir.rglob('*.yaml'))
    logger.info(f"Found {len(record_files)} record files")
    
    for record_file in sorted(record_files):
        # Skip file list files
        if record_file.name.endswith('_files.yaml'):
            continue
        
        record_data = load_yaml_file(record_file)
        if record_data and 'id' in record_data:
            records.append(record_data)
        else:
            logger.debug(f"Skipping invalid record file: {record_file}")
    
    logger.info(f"Loaded {len(records)} records")
    return records


def normalize_collections(collections: List[Dict]) -> List[Dict]:
    """Normalize collection data structures."""
    normalized = []
    
    for coll in collections:
        normalized_coll = {
            'id': coll.get('id', ''),
            'slug': coll.get('slug', ''),
            'name': coll.get('name', ''),
            'num_records': coll.get('num_records', 0),
        }
        
        # Add optional fields
        if 'created' in coll:
            normalized_coll['created'] = coll['created']
        if 'description' in coll:
            normalized_coll['description'] = coll['description']
        if 'collection_type' in coll:
            normalized_coll['collection_type'] = coll['collection_type']
        if 'collection_date' in coll:
            normalized_coll['collection_date'] = coll['collection_date']
        if 'reason' in coll:
            normalized_coll['reason'] = coll['reason']
        if 'reason_url' in coll:
            normalized_coll['reason_url'] = coll['reason_url']
        
        # Flatten files structure
        if 'files' in coll and isinstance(coll['files'], dict):
            files = coll['files']
            if 'total_count' in files:
                normalized_coll['files_total_count'] = files['total_count']
            if 'total_size' in files:
                normalized_coll['files_total_size'] = files['total_size']
            if 'directories' in files and isinstance(files['directories'], list):
                normalized_coll['files_directories'] = files['directories']
        
        normalized.append(normalized_coll)
    
    return normalized


def normalize_records(records: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    Normalize record data and extract resources.
    Returns: (normalized_records, resources)
    """
    normalized_records = []
    all_resources = []
    
    for record in records:
        # Extract collection info
        collection_info = record.get('collection', {})
        collection_id = collection_info.get('id', '') if isinstance(collection_info, dict) else ''
        collection_slug = collection_info.get('slug', '') if isinstance(collection_info, dict) else ''
        collection_name = collection_info.get('name', '') if isinstance(collection_info, dict) else ''
        
        # If collection is just a string, use it as slug
        if not collection_slug and isinstance(collection_info, str):
            collection_slug = collection_info
        
        normalized_record = {
            'id': record.get('id', ''),
            'name': record.get('name', ''),
            'collection_id': collection_id,
            'collection_slug': collection_slug,
            'collection_name': collection_name,
        }
        
        # Add optional fields
        if 'domain' in record:
            normalized_record['domain'] = record['domain']
        if 'url' in record:
            normalized_record['url'] = record['url']
        if 'created' in record:
            normalized_record['created'] = record['created']
        if 'date' in record:
            normalized_record['date'] = record['date']
        if 'status' in record:
            normalized_record['status'] = record['status']
        if 'status_id' in record:
            normalized_record['status_id'] = record['status_id']
        if 'resource_type' in record:
            normalized_record['resource_type'] = record['resource_type']
        if 'resource_type_id' in record:
            normalized_record['resource_type_id'] = record['resource_type_id']
        if 'reason' in record:
            normalized_record['reason'] = record['reason']
        if 'reason_id' in record:
            normalized_record['reason_id'] = record['reason_id']
        if 'reason_url' in record:
            normalized_record['reason_url'] = record['reason_url']
        if 'strategy' in record:
            normalized_record['strategy'] = record['strategy']
        if 'tools' in record:
            normalized_record['tools'] = record['tools']
        if 'format' in record:
            normalized_record['format'] = record['format']
        if 'format_id' in record:
            normalized_record['format_id'] = record['format_id']
        if 'source' in record:
            source = record['source']
            if isinstance(source, dict):
                normalized_record['source_id'] = source.get('id', '')
                normalized_record['source_name'] = source.get('name', '')
            else:
                normalized_record['source'] = source
        if 'priority' in record:
            normalized_record['priority'] = record['priority']
        if 'storage_url' in record:
            normalized_record['storage_url'] = record['storage_url']
        if 'cloud_url' in record:
            normalized_record['cloud_url'] = record['cloud_url']
        
        normalized_records.append(normalized_record)
        
        # Extract resources
        record_id = record.get('id', '')
        resources = record.get('resources', [])
        
        if isinstance(resources, list):
            for resource in resources:
                if isinstance(resource, dict):
                    normalized_resource = {
                        'record_id': record_id,
                        'name': resource.get('name', ''),
                        'url': resource.get('url', ''),
                        'size': resource.get('size', 0) or 0,
                    }
                    
                    if 'modified' in resource:
                        normalized_resource['modified'] = resource['modified']
                    if 'type' in resource:
                        normalized_resource['type'] = resource['type']
                    if 'extension' in resource:
                        normalized_resource['extension'] = resource['extension']
                    
                    all_resources.append(normalized_resource)
    
    logger.info(f"Extracted {len(all_resources)} resources from {len(normalized_records)} records")
    return normalized_records, all_resources


def export_jsonl(data: List[Dict], output_path: Path, compress: bool = True) -> None:
    """Export data to JSONL format, optionally compressed."""
    logger.info(f"Exporting {len(data)} items to JSONL: {output_path}")
    
    start_time = time.time()
    
    if compress and HAS_ZSTD:
        # Compressed JSONL
        cctx = zstd.ZstdCompressor()
        with open(output_path, 'wb') as f:
            with cctx.stream_writer(f) as compressor:
                for item in data:
                    line = json.dumps(item, ensure_ascii=False) + '\n'
                    compressor.write(line.encode('utf-8'))
    else:
        # Uncompressed JSONL
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in data:
                line = json.dumps(item, ensure_ascii=False) + '\n'
                f.write(line)
    
    elapsed = time.time() - start_time
    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
    logger.info(f"  Exported in {elapsed:.2f}s ({file_size:.2f} MB)")


def export_parquet(data: List[Dict], output_path: Path) -> None:
    """Export data to Parquet format."""
    logger.info(f"Exporting {len(data)} items to Parquet: {output_path}")
    
    start_time = time.time()
    
    if HAS_POLARS:
        # Use Polars
        df = pl.DataFrame(data)
        df.write_parquet(output_path, compression='zstd')
    elif HAS_PANDAS:
        # Use pandas
        df = pd.DataFrame(data)
        df.to_parquet(output_path, compression='zstd', engine='pyarrow')
    else:
        raise RuntimeError("Neither polars nor pandas available")
    
    elapsed = time.time() - start_time
    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
    logger.info(f"  Exported in {elapsed:.2f}s ({file_size:.2f} MB)")


def export_duckdb(collections: List[Dict], records: List[Dict], 
                  resources: List[Dict], output_path: Path, parquet_dir: Path) -> None:
    """Export data to DuckDB database with separate tables."""
    logger.info(f"Exporting to DuckDB: {output_path}")
    
    start_time = time.time()
    
    # Remove existing database if it exists
    if output_path.exists():
        output_path.unlink()
    
    # Connect to DuckDB
    conn = duckdb.connect(str(output_path))
    
    try:
        # Read from Parquet files (most reliable method)
        collections_parquet = parquet_dir / 'collections.parquet'
        records_parquet = parquet_dir / 'records.parquet'
        resources_parquet = parquet_dir / 'resources.parquet'
        
        # Create collections table
        logger.info("  Creating collections table...")
        if collections_parquet.exists():
            # Use absolute path for DuckDB
            parquet_path = str(collections_parquet.resolve())
            conn.execute(f"CREATE TABLE collections AS SELECT * FROM read_parquet('{parquet_path}')")
        else:
            # Fallback: use DataFrame directly
            if HAS_POLARS:
                collections_df = pl.DataFrame(collections)
                # Register as a view
                conn.register('collections_df', collections_df)
                conn.execute("CREATE TABLE collections AS SELECT * FROM collections_df")
            elif HAS_PANDAS:
                collections_df = pd.DataFrame(collections)
                conn.register('collections_df', collections_df)
                conn.execute("CREATE TABLE collections AS SELECT * FROM collections_df")
        
        # Create records table
        logger.info("  Creating records table...")
        if records_parquet.exists():
            parquet_path = str(records_parquet.resolve())
            conn.execute(f"CREATE TABLE records AS SELECT * FROM read_parquet('{parquet_path}')")
        else:
            if HAS_POLARS:
                records_df = pl.DataFrame(records)
                conn.register('records_df', records_df)
                conn.execute("CREATE TABLE records AS SELECT * FROM records_df")
            elif HAS_PANDAS:
                records_df = pd.DataFrame(records)
                conn.register('records_df', records_df)
                conn.execute("CREATE TABLE records AS SELECT * FROM records_df")
        
        # Create resources table
        logger.info("  Creating resources table...")
        if resources_parquet.exists():
            parquet_path = str(resources_parquet.resolve())
            conn.execute(f"CREATE TABLE resources AS SELECT * FROM read_parquet('{parquet_path}')")
        else:
            if HAS_POLARS:
                resources_df = pl.DataFrame(resources)
                conn.register('resources_df', resources_df)
                conn.execute("CREATE TABLE resources AS SELECT * FROM resources_df")
            elif HAS_PANDAS:
                resources_df = pd.DataFrame(resources)
                conn.register('resources_df', resources_df)
                conn.execute("CREATE TABLE resources AS SELECT * FROM resources_df")
        
        # Get table counts
        collections_count = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
        records_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        resources_count = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        
        logger.info(f"  Collections: {collections_count} rows")
        logger.info(f"  Records: {records_count} rows")
        logger.info(f"  Resources: {resources_count} rows")
        
    finally:
        conn.close()
    
    elapsed = time.time() - start_time
    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
    logger.info(f"  Exported in {elapsed:.2f}s ({file_size:.2f} MB)")


def build_datasets(project_root: Path, output_dir: Path) -> None:
    """Main build function."""
    logger.info("=" * 60)
    logger.info("Building datasets from collections and records")
    logger.info("=" * 60)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    logger.info("\nStep 1: Loading data...")
    collections = load_collections(project_root)
    records = load_records(project_root)
    
    if not collections:
        logger.warning("No collections found!")
    if not records:
        logger.warning("No records found!")
    
    # Normalize data
    logger.info("\nStep 2: Normalizing data...")
    normalized_collections = normalize_collections(collections)
    normalized_records, resources = normalize_records(records)
    
    logger.info(f"  Collections: {len(normalized_collections)}")
    logger.info(f"  Records: {len(normalized_records)}")
    logger.info(f"  Resources: {len(resources)}")
    
    # Export JSONL
    logger.info("\nStep 3: Exporting JSONL...")
    export_jsonl(normalized_collections, output_dir / 'collections.jsonl.zst', compress=True)
    export_jsonl(normalized_records, output_dir / 'records.jsonl.zst', compress=True)
    export_jsonl(resources, output_dir / 'resources.jsonl.zst', compress=True)
    
    # Export Parquet
    logger.info("\nStep 4: Exporting Parquet...")
    export_parquet(normalized_collections, output_dir / 'collections.parquet')
    export_parquet(normalized_records, output_dir / 'records.parquet')
    export_parquet(resources, output_dir / 'resources.parquet')
    
    # Export DuckDB
    logger.info("\nStep 5: Exporting DuckDB...")
    export_duckdb(normalized_collections, normalized_records, resources, 
                  output_dir / 'ruarxive.duckdb', output_dir)
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ Build complete!")
    logger.info(f"  Output directory: {output_dir}")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Build datasets from collections and records'
    )
    parser.add_argument(
        'command',
        choices=['build'],
        help='Command to execute'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/datasets',
        help='Output directory for datasets (default: data/datasets)'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Project root directory (default: current directory)'
    )
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root).resolve()
    output_dir = project_root / args.output_dir
    
    if args.command == 'build':
        build_datasets(project_root, output_dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
