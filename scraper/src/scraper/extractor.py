from bs4 import BeautifulSoup


def extract_products(soup: BeautifulSoup) -> list[dict]:
    results = []
    cards = soup.find_all("div", {"data-component-type": "s-search-result"})

    for card in cards:
        title_tag = card.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        a_tag = title_tag.find("a") if title_tag else None
        link = (
            ("https://www.amazon.com" + a_tag["href"])
            if a_tag and a_tag.get("href")
            else "N/A"
        )

        price_whole = card.find("span", class_="a-price-whole")
        price_fraction = card.find("span", class_="a-price-fraction")
        price_w = (
            price_whole.get_text(strip=True).replace(".", "") if price_whole else "N/A"
        )
        price_f = price_fraction.get_text(strip=True) if price_fraction else "N/A"

        rating_tag = card.find("span", {"class": "a-icon-alt"})
        rating = rating_tag.get_text(strip=True).split(" ")[0] if rating_tag else "N/A"

        num_ratings_tag = card.find("span", {"class": "a-size-base s-underline-text"})
        num_ratings = (
            num_ratings_tag.get_text(strip=True) if num_ratings_tag else "N/A"
        )

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
