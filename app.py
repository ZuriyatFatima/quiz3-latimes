from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
import re

app = Flask(__name__)

REGISTRATION = "FA23-BAI-054"
NEWS_SOURCE = "Los Angeles Times"

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service("/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def summarize(text, max_sentences=4):
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    summary = " ".join(sentences[:max_sentences])
    return summary if summary else text[:600]

def scrape_latimes(keyword):
    driver = get_driver()
    article_url = ""
    summary = ""
    try:
        search_url = f"https://www.latimes.com/search#nt=navsearch&q={keyword.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(5)
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href") or ""
                if ("latimes.com/" in href and
                    any(x in href for x in ["/story/", "/california/", "/world/",
                                            "/politics/", "/business/", "/sports/",
                                            "/entertainment/", "/science/", "/health/"]) and
                    href != "https://www.latimes.com/"):
                    article_url = href
                    break
        except Exception:
            pass
        if not article_url:
            return "", "No article found for the given keyword."
        driver.get(article_url)
        time.sleep(4)
        body_text = ""
        selectors = [
            ".rich-text-article-body p",
            ".article-body p",
            ".story-body p",
            ".page-article-body p",
            "article p",
            "main p",
            "p"
        ]
        for sel in selectors:
            try:
                paragraphs = driver.find_elements(By.CSS_SELECTOR, sel)
                candidate = " ".join(
                    p.text.strip() for p in paragraphs
                    if p.text.strip() and len(p.text.strip()) > 30
                )
                if len(candidate) > 150:
                    body_text = candidate
                    break
            except Exception:
                continue
        if not body_text:
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                pass
        summary = summarize(body_text) if body_text else "Could not extract article content."
    finally:
        driver.quit()
    return article_url, summary

@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "keyword parameter is required"}), 400
    try:
        url, summary = scrape_latimes(keyword)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "keyword": keyword,
        "url": url,
        "summary": summary
    })

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "message": "Selenium News Scraper API. Use /get?keyword=<keyword>"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=False)
