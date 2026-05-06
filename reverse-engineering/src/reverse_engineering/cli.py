from reverse_engineering.api import fetch_all_courses, graphql_sample
from reverse_engineering.config import Config
from reverse_engineering.storage import load_bigquery, save_csv, upload_gcs
from reverse_engineering.transform import build_dataframe


def main() -> None:
    config = Config()

    print("=" * 55)
    print("  Coursera API Extraction")
    print("=" * 55)

    print("\n[1/5] GraphQL sample request (DevTools-discovered)...")
    try:
        gql_data = graphql_sample(config, start=0, limit=3)
        elements = (
            gql_data.get("data", {}).get("DiscoveryCollections", {}).get("elements", [])
        )
        print(f"  GraphQL returned {len(elements)} sample elements")
        if elements:
            print(f"  First: {elements[0].get('name')} | {elements[0].get('slug')}")
    except Exception as exc:
        print(f"  GraphQL demo skipped: {exc}")

    print("\n[2/5] Bulk fetch via REST v1 API...")
    raw = fetch_all_courses(config)

    print("\n[3/5] Normalizing & building DataFrame...")
    df = build_dataframe(raw)
    if df.empty:
        print("  No courses fetched - all pages failed. Check network/auth.")
        return
    print(
        df[["course_id", "name", "course_status", "primary_languages"]]
        .head(5)
        .to_string()
    )

    print("\n[4/5] Saving CSV...")
    save_csv(df, config.csv_filename)

    print("\n[5/5] Uploading to GCS & BigQuery...")
    if config.gcp_project_id == "YOUR_PROJECT_ID":
        print("  GCP_PROJECT_ID not set - skipping cloud upload.")
        print("  Update the config and rerun.")
    else:
        gcs_uri = upload_gcs(config, config.csv_filename)
        table_id = load_bigquery(config, gcs_uri)
        print(f"\n  Query your data:")
        print(f"  SELECT * FROM `{table_id}` LIMIT 10")

    print("\nDone.")


if __name__ == "__main__":
    main()
