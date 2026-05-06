import undetected_chromedriver as uc

from scraper.config import ScraperConfig


def build_driver(config: ScraperConfig) -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument(f"--window-size={config.window_width},{config.window_height}")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    if config.headless:
        options.add_argument("--headless=chrome")

    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
        version_main=config.chrome_version,
    )

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
