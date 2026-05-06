import os
import urllib.parse
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.config import ScraperConfig
from scraper.driver import build_driver
from scraper.extractor import extract_products
from scraper.utils import is_blocked, random_delay


def scrape(config: ScraperConfig) -> None:
    print(f"Keyword : {config.keyword}")
    print(f"Pages   : {config.pages}\n")

    os.makedirs(config.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = config.keyword.replace(" ", "_")
    csv_file = os.path.join(config.output_dir, f"amazon_{slug}_{timestamp}.csv")
    html_file = os.path.join(config.output_dir, f"amazon_{slug}_{timestamp}.html")

    driver = build_driver(config)
    wait = WebDriverWait(driver, config.wait_timeout)

    all_products: list[dict] = []
    all_html_pages: list[str] = []

    try:
        encoded_kw = urllib.parse.quote_plus(config.keyword)

        print("Warming up on amazon.com ...")
        driver.get("https://www.amazon.com")
        random_delay(config.warmup_delay_lo, config.warmup_delay_hi)

        for page_num in range(1, config.pages + 1):
            url = f"https://www.amazon.com/s?k={encoded_kw}&page={page_num}"
            print(f"Scraping page {page_num} -> {url}")

            driver.get(url)
            random_delay(config.page_delay_lo, config.page_delay_hi)

            page_source = driver.page_source

            if is_blocked(page_source):
                print(f"CAPTCHA detected - screenshot saved, stopping.")
                driver.save_screenshot(
                    os.path.join(config.output_dir, f"blocked_p{page_num}.png")
                )
                break

            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                    )
                )
            except Exception:
                print(f"No product cards found on page {page_num} - skipping.")
                driver.save_screenshot(
                    os.path.join(config.output_dir, f"nocard_p{page_num}.png")
                )
                continue

            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight / 2);"
            )
            random_delay(config.scroll_delay_lo, config.scroll_delay_hi)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            random_delay(config.scroll_delay_lo, config.scroll_delay_hi)

            page_html = driver.page_source
            all_html_pages.append(
                f"\n\n<!-- ========== PAGE {page_num}: {url} ========== -->\n"
                + page_html
            )

            products = extract_products(BeautifulSoup(page_html, "html.parser"))
            all_products.extend(products)
            print(f"  {len(products)} products  (total: {len(all_products)})")

            random_delay(
                config.between_page_delay_lo, config.between_page_delay_hi
            )

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    except Exception as exc:
        print(f"\nError: {exc}")
        driver.save_screenshot(os.path.join(config.output_dir, "error.png"))
        raise

    finally:
        driver.quit()
        print("\nBrowser closed")

    if all_products:
        df = pd.DataFrame(all_products)
        df["Price_Whole"] = df["Price_Whole"].str.replace(",", "", regex=False)
        df["Num_Ratings"] = df["Num_Ratings"].str.replace(",", "", regex=False)
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"\nCSV  saved -> {csv_file}  ({len(df)} rows)")
    else:
        print("\nNo products collected.")
        return

    if all_html_pages:
        with open(html_file, "w", encoding="utf-8") as f:
            f.write("\n".join(all_html_pages))
        print(
            f"HTML saved -> {html_file}  ({os.path.getsize(html_file) / 1024:.1f} KB)"
        )

    df["Price"] = pd.to_numeric(df["Price_Whole"], errors="coerce")
    df["Stars"] = pd.to_numeric(df["Rating"], errors="coerce")
    print(f"\nSummary")
    print(f"   Products : {len(df)}")
    print(f"   Avg price: ${df['Price'].mean():.2f}")
    print(f"   Avg stars: {df['Stars'].mean():.2f}")
