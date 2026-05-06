from dataclasses import dataclass, field


@dataclass
class ScraperConfig:
    keyword: str = "mechanical keyboard"
    pages: int = 3
    output_dir: str = "amazon_output"
    headless: bool = False
    delay_lo: float = 2.0
    delay_hi: float = 5.0
    warmup_delay_lo: float = 3.0
    warmup_delay_hi: float = 5.0
    page_delay_lo: float = 3.0
    page_delay_hi: float = 6.0
    scroll_delay_lo: float = 1.0
    scroll_delay_hi: float = 2.0
    between_page_delay_lo: float = 2.0
    between_page_delay_hi: float = 5.0
    wait_timeout: int = 20
    window_width: int = 1920
    window_height: int = 1080
    chrome_version: int = 147
