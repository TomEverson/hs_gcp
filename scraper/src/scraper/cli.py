from scraper.config import ScraperConfig
from scraper.scraper import scrape


def main() -> None:
    config = ScraperConfig()
    scrape(config)


if __name__ == "__main__":
    main()
