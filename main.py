import os
import random
import time
import urllib.parse
from datetime import datetime

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ============================================================
# CONFIG — edit these
# ============================================================
KEYWORD = "mechanical keyboard"
PAGES = 3
OUTPUT_DIR = "amazon_output"
HEADLESS = False  # ⚠️  keep False — Amazon blocks headless aggressively
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
slug = KEYWORD.replace(" ", "_")
CSV_FILE = os.path.join(OUTPUT_DIR, f"amazon_{slug}_{timestamp}.csv")
HTML_FILE = os.path.join(OUTPUT_DIR, f"amazon_{slug}_{timestamp}.html")


def build_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    if HEADLESS:
        # use old headless flag — new headless is easier to detect
        options.add_argument("--headless=chrome")

    driver = uc.Chrome(options=options, use_subprocess=True, version_main=147)

    # Mask a few extra JS properties
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """
        },
    )
    return driver


def random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
    time.sleep(random.uniform(lo, hi))


def is_blocked(source: str) -> bool:
    src = source.lower()
    return any(
        k in src
        for k in [
            "robot check",
            "captcha",
            "enter the characters you see below",
            "sorry, we just need to make sure",
            "automated access",
        ]
    )


def extract_products(soup: BeautifulSoup) -> list[dict]:
    results = []
    cards = soup.find_all("div", {"data-component-type": "s-search-result"})

    for card in cards:
        # Title
        title_tag = card.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        # Link
        a_tag = title_tag.find("a") if title_tag else None
        link = (
            ("https://www.amazon.com" + a_tag["href"])
            if a_tag and a_tag.get("href")
            else "N/A"
        )

        # Price whole + fraction
        price_whole = card.find("span", class_="a-price-whole")
        price_fraction = card.find("span", class_="a-price-fraction")
        price_w = (
            price_whole.get_text(strip=True).replace(".", "") if price_whole else "N/A"
        )
        price_f = price_fraction.get_text(strip=True) if price_fraction else "N/A"

        # Rating (e.g. "4.5 out of 5 stars" → "4.5")
        rating_tag = card.find("span", {"class": "a-icon-alt"})
        rating = rating_tag.get_text(strip=True).split(" ")[0] if rating_tag else "N/A"

        # Number of ratings
        num_ratings_tag = card.find("span", {"class": "a-size-base s-underline-text"})
        num_ratings = num_ratings_tag.get_text(strip=True) if num_ratings_tag else "N/A"

        results.append(
            {
                "Title": title,
                "Link": link,
                "Price_Whole": price_w,
                "Price_Fraction": price_f,
                "Rating": rating,
                "Num_Ratings": num_ratings,
            }
        )

    return results


def scrape() -> None:
    print(f"🔑 Keyword : {KEYWORD}")
    print(f"📄 Pages   : {PAGES}\n")

    driver = build_driver()
    wait = WebDriverWait(driver, 20)

    all_products: list[dict] = []
    all_html_pages: list[str] = []

    try:
        encoded_kw = urllib.parse.quote_plus(KEYWORD)

        # Warm up — visit homepage first like a real user
        print("🌐 Warming up on amazon.com ...")
        driver.get("https://www.amazon.com")
        random_delay(3, 5)

        for page_num in range(1, PAGES + 1):
            url = f"https://www.amazon.com/s?k={encoded_kw}&page={page_num}"
            print(f"📄 Scraping page {page_num} → {url}")

            driver.get(url)
            random_delay(3, 6)

            page_source = driver.page_source

            if is_blocked(page_source):
                print("   ⚠️  CAPTCHA detected — screenshot saved, stopping.")
                driver.save_screenshot(
                    os.path.join(OUTPUT_DIR, f"blocked_p{page_num}.png")
                )
                break

            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                    )
                )
            except Exception:
                print(f"   ⚠️  No product cards found on page {page_num} — skipping.")
                driver.save_screenshot(
                    os.path.join(OUTPUT_DIR, f"nocard_p{page_num}.png")
                )
                continue

            # Scroll down naturally to load lazy images
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            random_delay(1, 2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            random_delay(1, 2)

            page_html = driver.page_source
            all_html_pages.append(
                f"\n\n<!-- ========== PAGE {page_num}: {url} ========== -->\n"
                + page_html
            )

            products = extract_products(BeautifulSoup(page_html, "html.parser"))
            all_products.extend(products)
            print(f"   ✅ {len(products)} products  (total: {len(all_products)})")

            random_delay(2, 5)

    except KeyboardInterrupt:
        print("\n⛔ Interrupted by user.")

    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        driver.save_screenshot(os.path.join(OUTPUT_DIR, "error.png"))
        raise

    finally:
        driver.quit()
        print("\n🛑 Browser closed")

    # ── Save CSV ──────────────────────────────────────────────
    if all_products:
        df = pd.DataFrame(all_products)
        df["Price_Whole"] = df["Price_Whole"].str.replace(",", "", regex=False)
        df["Num_Ratings"] = df["Num_Ratings"].str.replace(",", "", regex=False)
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        print(f"\n💾 CSV  saved → {CSV_FILE}  ({len(df)} rows)")
    else:
        print("\n⚠️  No products collected.")
        return

    # ── Save HTML ─────────────────────────────────────────────
    if all_html_pages:
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(all_html_pages))
        print(
            f"💾 HTML saved → {HTML_FILE}  ({os.path.getsize(HTML_FILE) / 1024:.1f} KB)"
        )

    # ── Summary ───────────────────────────────────────────────
    df["Price"] = pd.to_numeric(df["Price_Whole"], errors="coerce")
    df["Stars"] = pd.to_numeric(df["Rating"], errors="coerce")
    print(f"\n📊 Summary")
    print(f"   Products : {len(df)}")
    print(f"   Avg price: ${df['Price'].mean():.2f}")
    print(f"   Avg stars: {df['Stars'].mean():.2f} ⭐")


if __name__ == "__main__":
    scrape()
