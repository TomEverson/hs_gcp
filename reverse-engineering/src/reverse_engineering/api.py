import time

import requests
from tqdm import tqdm

from reverse_engineering.config import Config


def fetch_page(config: Config, start: int = 0, limit: int = 100) -> dict:
    resp = requests.get(
        config.courses_v1_url,
        headers=config.headers,
        params={
            "fields": config.courses_v1_fields,
            "start": start,
            "limit": limit,
            "includes": "partnerIds",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def graphql_sample(config: Config, start: int = 0, limit: int = 12) -> dict:
    resp = requests.post(
        config.graphql_url,
        headers=config.graphql_headers,
        params={"opname": "DiscoveryCollections"},
        json={
            "operationName": "DiscoveryCollections",
            "variables": {
                "contextType": "TOPIC",
                "contextId": "data-science",
                "start": start,
                "limit": limit,
            },
            "query": config.graphql_query,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_all_courses(config: Config) -> list[dict]:
    all_courses, errors = [], []

    with tqdm(total=config.total_pages, desc="Fetching pages") as bar:
        for page in range(config.total_pages):
            try:
                data = fetch_page(
                    config, start=page * config.page_size, limit=config.page_size
                )
                elements = data.get("elements", [])
                all_courses.extend(elements)
                bar.set_postfix(total=len(all_courses))
                if len(elements) < config.page_size:
                    print(f"\n  Last page at {page} ({len(elements)} items)")
                    bar.update(1)
                    break
            except requests.HTTPError as exc:
                errors.append((page, str(exc)))
                print(f"\n  Page {page} failed: {exc}")
            finally:
                bar.update(1)
                time.sleep(config.sleep_between)

    print(f"Fetched {len(all_courses)} courses | {len(errors)} errors")
    return all_courses
