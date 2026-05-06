# Coursera API Reverse Engineering

Reverse-engineered Coursera APIs to fetch course data, transform it, and load into GCP (GCS + BigQuery).

## Quick Start

```bash
uv run coursera
```

Or run directly:

```bash
uv run python -m reverse_engineering.cli
```

## Configuration

Edit `src/reverse_engineering/config.py` to change GCP project, bucket, dataset, and pagination settings.

## Pipeline

1. **GraphQL sample** - Demonstrates the internal GraphQL endpoint discovered via DevTools
2. **REST v1 bulk fetch** - Paginates through `api.coursera.org/api/courses.v1`
3. **Transform** - Normalizes fields, deduplicates by course_id
4. **CSV** - Saves locally
5. **GCS + BigQuery** - Uploads to Cloud Storage, loads into BigQuery

## Project Structure

```
reverse-engineering/
├── src/reverse_engineering/
│   ├── __init__.py
│   ├── cli.py          # Entry point
│   ├── config.py       # All configuration
│   ├── api.py          # REST + GraphQL API calls
│   ├── transform.py    # Normalization & DataFrame
│   └── storage.py      # CSV, GCS, BigQuery
├── tests/
├── pyproject.toml
└── README.md
```

## APIs Discovered

| Endpoint | Type | Purpose |
|---|---|---|
| `api.coursera.org/api/courses.v1` | REST | Public course listing with pagination |
| `coursera.org/graphql-gateway/v2` | GraphQL | Internal discovery collections |
