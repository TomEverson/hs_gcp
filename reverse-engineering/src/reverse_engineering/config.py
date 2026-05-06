from dataclasses import dataclass, field

from google.cloud import bigquery


@dataclass
class Config:
    gcp_project_id: str = "data-engineering-hs"
    gcs_bucket_name: str = "de-hs-ws-bucket"
    gcs_folder: str = "coursera/raw"
    bq_dataset: str = "coursera_data"
    bq_table: str = "courses"
    bq_location: str = "US"
    total_pages: int = 10
    page_size: int = 100
    sleep_between: float = 1.2
    csv_filename: str = "coursera_courses.csv"
    graphql_url: str = "https://www.coursera.org/graphql-gateway/v2"
    courses_v1_url: str = "https://api.coursera.org/api/courses.v1"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    graphql_query: str = """
query DiscoveryCollections(
  $contextType: String
  $contextId: String
  $start: Int
  $limit: Int
) {
  DiscoveryCollections(
    input: {
      contextType: $contextType
      contextId: $contextId
      start: $start
      limit: $limit
    }
  ) {
    elements {
      id
      label
      productType
      slug
      name
      tagline
      averageFiveStarRating
      ratingCount
      enrolledCount
      photoUrl
      difficultyLevel
      isCourseFree
      partners { id name shortName }
    }
    paging { total next }
  }
}
"""
    courses_v1_fields: str = (
        "id,name,slug,photoUrl,courseStatus,startDate,workload,"
        "previewLink,isGeorestricted,partnerIds,"
        "primaryLanguages,subtitleLanguages,certificates,description"
    )
    bq_schema: list = field(default_factory=lambda: [
        bigquery.SchemaField("course_id", "STRING"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("slug", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("course_status", "STRING"),
        bigquery.SchemaField("workload", "STRING"),
        bigquery.SchemaField("start_date", "STRING"),
        bigquery.SchemaField("primary_languages", "STRING"),
        bigquery.SchemaField("subtitle_languages", "STRING"),
        bigquery.SchemaField("certificates", "STRING"),
        bigquery.SchemaField("partner_ids", "STRING"),
        bigquery.SchemaField("partner_count", "INTEGER"),
        bigquery.SchemaField("photo_url", "STRING"),
        bigquery.SchemaField("preview_link", "STRING"),
        bigquery.SchemaField("is_georestricted", "BOOLEAN"),
        bigquery.SchemaField("extracted_at", "TIMESTAMP"),
    ])

    @property
    def headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @property
    def graphql_headers(self) -> dict:
        return {
            **self.headers,
            "Content-Type": "application/json",
            "X-Coursera-Application-Name": "browse",
            "Referer": "https://www.coursera.org/browse",
            "Origin": "https://www.coursera.org",
        }
