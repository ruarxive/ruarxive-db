#!/usr/bin/env python3
"""
Build the export consumed by the project website (ruarxive.org).

Sources are the storage file lists in data/filelists/:
- files_YYYYMMDD_HHMMSS.jsonl.zst — SFTP snapshots made by dev/scripts/collect_files.py;
- allarchives_YYYYMMDD.csv.zst — copies of the registry https://cdn.ruarxive.org/public/allarchives.csv.

For every top-level storage folder the newest listing that contains it is used, so a partial
snapshot only replaces the folders it actually covers. Collection names and catalog size come
from data/collections/ and data/records/, known top-level folders from data/reference/dirlist.txt.

Output (schema: docs/SITE_EXPORT.md):
- data/datasets/site/summary.json   — aggregate statistics
- data/datasets/site/resources.json — per-resource index for the website search

Requires: pyyaml, zstandard.
"""

import argparse
import csv
import io
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import yaml
import zstandard as zstd

SCHEMA_VERSION = 1
REPO_URL = 'https://github.com/ruarxive/ruarxive-db'
REGISTRY_URL = 'https://cdn.ruarxive.org/public/allarchives.csv'
PUBLIC_PREFIX = 'https://cdn.ruarxive.org/public/'
STORAGE_PREFIX = '/pool2/archive/public/'
REGISTRY_COLUMNS = ['id', 'collection', 'domain', 'filename', 'filesize', 'date_modified', 'public_url']

SNAPSHOT_RE = re.compile(r'^files_(\d{4})(\d{2})(\d{2})_\d{6}\.jsonl\.zst$')
REGISTRY_RE = re.compile(r'^allarchives_(\d{4})(\d{2})(\d{2})\.csv\.zst$')
# Crawl folders are named <domain>-<YYYY-MM-DD>-<8 hex>, e.g. pfrf.ru-2017-05-13-7795cadf
CRAWL_DIR_SUFFIX = re.compile(r'-\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$')
ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

FORMAT_GROUPS = [
    ('warc', 'WARC', re.compile(r'\.warc(\.gz|\.zst)?$')),
    ('db', 'Базы данных', re.compile(r'\.(db|sqlite|sqlite3|duckdb|parquet)(\.gz|\.xz|\.7z)?$')),
    ('index', 'Индексы CDX', re.compile(r'\.(cdx|cdxj|idx)(\.gz)?$')),
    ('packed', 'Архивы (7z, xz, zip и др.)', re.compile(r'\.(7z|zip|xz|gz|tgz|tar|bz2|lzo|srep|zst|rar)$')),
    ('log', 'Логи сбора', re.compile(r'\.log(\.gz)?$')),
]
OTHER_FORMAT = ('other', 'Прочее')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def read_zst_text(path: Path) -> Iterator[str]:
    with open(path, 'rb') as f:
        reader = zstd.ZstdDecompressor().stream_reader(f)
        yield from io.TextIOWrapper(reader, encoding='utf-8', newline='')


def classify_path(rel: str) -> Dict[str, str]:
    """Collection and resource for a storage path, following the conventions of allarchives.csv."""
    parts = rel.split('/')
    top, file = parts[0], parts[-1]
    strip_ext = lambda name: re.sub(r'\.[^.]+$', '', name)
    if len(parts) <= 2:
        return {'top': top, 'collection': top, 'domain': strip_ext(file)}
    if len(parts) == 3:
        return {'top': top, 'collection': parts[1], 'domain': strip_ext(file)}
    return {'top': top, 'collection': parts[1], 'domain': CRAWL_DIR_SUFFIX.sub('', parts[2])}


def row(top: str, collection: str, domain: str, filename: str, size: int, modified: str, rel: str) -> Dict:
    return {
        'top': top,
        'collection': collection,
        'domain': domain.lower(),
        'filename': filename,
        'bytes': size,
        'date': modified[:10],
        'dir': rel[: rel.rfind('/') + 1],
    }


def load_snapshot(path: Path, listing_date: str) -> Dict:
    # The collector repeats a file once per ancestor folder (source_directory), so dedupe by path.
    by_path: Dict[str, Dict] = {}
    for line in read_zst_text(path):
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get('path', '').startswith(STORAGE_PREFIX) and isinstance(item.get('size'), int):
            by_path[item['path']] = item

    rows = []
    for item in by_path.values():
        rel = item['path'][len(STORAGE_PREFIX):]
        c = classify_path(rel)
        rows.append(row(c['top'], c['collection'], c['domain'], item['filename'], item['size'], item['modified'], rel))
    return {
        'kind': 'snapshot',
        'file': path.name,
        # data/filelists/ is not committed, so link the repository rather than the file.
        'url': REPO_URL,
        'date': listing_date,
        'rows': rows,
        'skippedRows': 0,
    }


def load_registry(path: Path, listing_date: str) -> Dict:
    reader = csv.reader(read_zst_text(path))
    header = next(reader)
    if header != REGISTRY_COLUMNS:
        raise ValueError(f'{path.name}: unexpected columns {header}')

    rows, skipped = [], 0
    for r in reader:
        if not r:
            continue
        if len(r) != len(REGISTRY_COLUMNS) or not r[4].isdigit() or not ISO_DATE.match(r[5][:10]):
            skipped += 1
            continue
        _, collection, domain, filename, size, modified, public_url = r
        rel = public_url[len(PUBLIC_PREFIX):] if public_url.startswith(PUBLIC_PREFIX) else public_url
        # Some registry rows have an empty domain; recover it from the path. In dataportals/<portal>/<date>/
        # the path segment is a date and the collection code is the portal domain.
        resource = domain.strip()
        if not resource:
            derived = classify_path(rel)['domain']
            resource = collection if ISO_DATE.match(derived) else derived
        rows.append(row(rel.split('/')[0], collection, resource, filename, int(size), modified, rel))
    return {
        'kind': 'registry',
        'file': path.name,
        'url': REGISTRY_URL,
        'date': listing_date,
        'rows': rows,
        'skippedRows': skipped,
    }


def load_listings(filelists_dir: Path) -> List[Dict]:
    listings = []
    for path in sorted(filelists_dir.iterdir()):
        for pattern, loader in ((SNAPSHOT_RE, load_snapshot), (REGISTRY_RE, load_registry)):
            m = pattern.match(path.name)
            if m:
                listing_date = '-'.join(m.groups())
                logger.info(f'Loading {path.name}')
                listings.append(loader(path, listing_date))
    if not listings:
        raise FileNotFoundError(f'No file lists in {filelists_dir}')
    return sorted(listings, key=lambda s: s['date'], reverse=True)


def load_catalog(project_root: Path) -> Dict:
    names = {}
    for path in sorted((project_root / 'data' / 'collections').glob('*.yaml')):
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        if data.get('slug'):
            names[data['slug']] = data.get('name') or data['slug']

    records = 0
    for path in (project_root / 'data' / 'records').rglob('*.yaml'):
        if path.name.endswith('_files.yaml'):
            continue
        with open(path, encoding='utf-8') as f:
            if (yaml.safe_load(f) or {}).get('id'):
                records += 1
    return {'names': names, 'records': records}


def common_dir(a: str, b: str) -> str:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    prefix = a[:i]
    return prefix[: prefix.rfind('/') + 1]


def format_key(filename: str) -> str:
    lower = filename.lower()
    for key, _, pattern in FORMAT_GROUPS:
        if pattern.search(lower):
            return key
    return OTHER_FORMAT[0]


def build(project_root: Path, output_dir: Path) -> None:
    listings = load_listings(project_root / 'data' / 'filelists')

    claimed = set()
    rows: List[Dict] = []
    for listing in listings:
        tops = {r['top'] for r in listing['rows']}
        listing['dirs'] = sorted(tops - claimed)
        claimed |= tops
        listing['used'] = [r for r in listing['rows'] if r['top'] in listing['dirs']]
        rows.extend(listing['used'])

    years: Dict[str, Dict] = defaultdict(lambda: {'bytes': 0, 'files': 0})
    formats: Dict[str, int] = defaultdict(int)
    collections: Dict[str, Dict] = {}
    domains: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in rows:
        y = years[r['date'][:4]]
        y['bytes'] += r['bytes']
        y['files'] += 1
        formats[format_key(r['filename'])] += r['bytes']

        c = collections.setdefault(r['collection'], {'bytes': 0, 'files': 0, 'domains': set(), 'dir': r['dir']})
        c['bytes'] += r['bytes']
        c['files'] += 1
        c['dir'] = common_dir(c['dir'], r['dir'])
        if r['domain']:
            c['domains'].add(r['domain'])

        if not r['domain']:
            continue
        e = domains[r['domain']].setdefault(
            r['collection'], {'dir': r['dir'], 'files': 0, 'bytes': 0, 'first': r['date'], 'last': r['date']}
        )
        e['dir'] = common_dir(e['dir'], r['dir'])
        e['files'] += 1
        e['bytes'] += r['bytes']
        e['first'] = min(e['first'], r['date'])
        e['last'] = max(e['last'], r['date'])

    catalog = load_catalog(project_root)
    names = catalog['names']
    dirlist_path = project_root / 'data' / 'reference' / 'dirlist.txt'
    dirlist = [s.strip() for s in dirlist_path.read_text(encoding='utf-8').splitlines() if s.strip()]
    generated_at = date.today().isoformat()

    summary = {
        'schemaVersion': SCHEMA_VERSION,
        'generatedAt': generated_at,
        'sources': [
            {
                'kind': s['kind'],
                'file': s['file'],
                'url': s['url'],
                'date': s['date'],
                'dirs': s['dirs'],
                'files': len(s['used']),
                'bytes': sum(r['bytes'] for r in s['used']),
                'skippedRows': s['skippedRows'],
            }
            for s in listings
            if s['dirs']
        ],
        'unknownDirs': sorted(d for d in dirlist if d not in claimed),
        'catalog': {
            'url': REPO_URL,
            'collections': len(names),
            'records': catalog['records'],
            'uncatalogued': sum(1 for slug in collections if slug not in names),
        },
        'totals': {
            'bytes': sum(r['bytes'] for r in rows),
            'files': len(rows),
            'domains': len(domains),
            'collections': len(collections),
        },
        'byYear': [{'year': y, **v} for y, v in sorted(years.items())],
        'collections': [
            {
                'name': slug,
                'title': names.get(slug),
                'bytes': c['bytes'],
                'files': c['files'],
                'domains': len(c['domains']),
                'dir': c['dir'],
            }
            for slug, c in sorted(collections.items(), key=lambda kv: kv[1]['bytes'], reverse=True)
        ],
        'formats': [
            {'key': key, 'label': label, 'bytes': formats[key]}
            for key, label, *_ in [*FORMAT_GROUPS, OTHER_FORMAT]
            if formats[key] > 0
        ],
    }

    # Compact rows: [domain, [[collection, dir, files, bytes, firstDate, lastDate], ...]];
    # dir is '' when the files have no common folder under publicPrefix.
    resources = {
        'schemaVersion': SCHEMA_VERSION,
        'generatedAt': generated_at,
        'publicPrefix': PUBLIC_PREFIX,
        'collectionNames': {slug: name for slug, name in sorted(names.items()) if slug in collections},
        'domains': [
            [
                domain,
                [
                    [slug, e['dir'], e['files'], e['bytes'], e['first'], e['last']]
                    for slug, e in sorted(per_domain.items(), key=lambda kv: kv[1]['bytes'], reverse=True)
                ],
            ]
            for domain, per_domain in sorted(domains.items())
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write('\n')
    with open(output_dir / 'resources.json', 'w', encoding='utf-8') as f:
        json.dump(resources, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')

    for s in summary['sources']:
        logger.info(f"{s['file']} ({s['date']}): {len(s['dirs'])} folders, {s['files']} files, {s['bytes'] / 1e12:.2f} TB")
    if summary['unknownDirs']:
        logger.info(f"No file list for: {', '.join(summary['unknownDirs'])}")
    t = summary['totals']
    logger.info(
        f"Total: {t['files']} files, {t['bytes'] / 1e12:.2f} TB, {t['domains']} resources, {t['collections']} collections"
    )
    logger.info(f'Written to {output_dir}')


def check(output_dir: Path) -> List[str]:
    """Validate an existing export without the source file lists; returns a list of problems."""
    problems = []
    try:
        with open(output_dir / 'summary.json', encoding='utf-8') as f:
            summary = json.load(f)
        with open(output_dir / 'resources.json', encoding='utf-8') as f:
            resources = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [str(e)]

    for name, data, keys in (
        ('summary.json', summary,
         ['generatedAt', 'sources', 'unknownDirs', 'catalog', 'totals', 'byYear', 'collections', 'formats']),
        ('resources.json', resources, ['generatedAt', 'publicPrefix', 'collectionNames', 'domains']),
    ):
        if data.get('schemaVersion') != SCHEMA_VERSION:
            problems.append(f"{name}: schemaVersion {data.get('schemaVersion')}, expected {SCHEMA_VERSION}")
        problems += [f'{name}: missing {key}' for key in keys if key not in data]
    if problems:
        return problems

    totals = summary['totals']
    for label, value in (
        ('sources.bytes', sum(s['bytes'] for s in summary['sources'])),
        ('collections.bytes', sum(c['bytes'] for c in summary['collections'])),
        ('byYear.bytes', sum(y['bytes'] for y in summary['byYear'])),
        ('formats.bytes', sum(f['bytes'] for f in summary['formats'])),
    ):
        if value != totals['bytes']:
            problems.append(f"summary.json: {label} = {value}, totals.bytes = {totals['bytes']}")
    if len(summary['collections']) != totals['collections']:
        problems.append(f"summary.json: {len(summary['collections'])} collections, totals say {totals['collections']}")
    if len(resources['domains']) != totals['domains']:
        problems.append(f"resources.json: {len(resources['domains'])} resources, totals say {totals['domains']}")
    if summary['generatedAt'] != resources['generatedAt']:
        problems.append('summary.json and resources.json come from different runs')
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Build the website export (summary.json, resources.json)')
    parser.add_argument('--project-root', default='.', help='Project root directory (default: current directory)')
    parser.add_argument(
        '--output-dir', default='data/datasets/site', help='Output directory (default: data/datasets/site)'
    )
    parser.add_argument(
        '--check', action='store_true', help='Validate the existing export instead of building it'
    )
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()
    output_dir = project_root / args.output_dir

    if args.check:
        problems = check(output_dir)
        for problem in problems:
            logger.error(problem)
        if not problems:
            logger.info(f'{output_dir}: export is valid')
        return 1 if problems else 0

    build(project_root, output_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
