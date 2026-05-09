from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

app = Flask(__name__)

# Registration details for FA23-BAI-054
REGISTRATION = "FA23-BAI-054"
NEWS_SOURCE = "Los Angeles Times"

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    service = Service("/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def simple_summarize(text, max_sentences=4):
    if not text or len(text) < 150:
        return "Extraction failed or content was blocked by a paywall/overlay."
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean_sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    summary = ' '.join(clean_sentences[:max_sentences])
    return summary if len(summary) > 20 else text[:500]

def scrape_latimes(keyword):
    driver = get_chrome_driver()
    article_url = ""
    summary = ""
    try:
        # 1. Search with relevance sorting
        search_url = f"https://www.latimes.com/search?q={keyword.replace(' ', '+')}&s=1"
        driver.get(search_url)
        
        wait = WebDriverWait(driver, 15)
        # 2. Pick the most relevant article link
        links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.promo-title-link, .promo-title a, .card-headline a")))
        
        article_link = None
        for link in links:
            href = link.get_attribute("href") or ""
            if "latimes.com" in href and "/story/" in href:
                article_link = href
                break
        
        if not article_link:
            return "", "No relevant article found."

        article_url = article_link
        driver.get(article_url)
        time.sleep(5)

        # 3. Aggressive cleanup of overlays/banners using JS
        driver.execute_script("""
            var selectors = ['.fc-ab-root', '.tp-modal', '.tp-backdrop', '#onetrust-consent-sdk', '.paywall-overlay'];
            selectors.forEach(sel => {
                var el = document.querySelector(sel);
                if(el) el.remove();
            });
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        """)
        
        # Scroll to wake up lazy-loaded content
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(3)

        # 4. Extract content using multiple selector attempts
        paragraphs = []
        body_selectors = [
            "div.rich-text-article-body-content p",
            "div.article-body p",
            "div.rich-text-body p",
            "div[data-element='article-body'] p",
            "article p",
            "main p"
        ]
        
        for sel in body_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            text_list = [e.text.strip() for e in elements if len(e.text.strip()) > 35]
            if len(text_list) > 2:
                paragraphs = text_list
                break
        
        if not paragraphs:
            # Fallback to general p tags if specific wrappers fail
            elements = driver.find_elements(By.TAG_NAME, "p")
            paragraphs = [e.text.strip() for e in elements if len(e.text.strip()) > 60]

        full_text = ' '.join(paragraphs)
        summary = simple_summarize(full_text)

    except Exception as e:
        summary = f"Scraper error: {str(e)}"
    finally:
        driver.quit()
    return article_url, summary

@app.route('/get', methods=['GET'])
def get_news():
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({"error": "Keyword required"}), 400
    
    url, summary = scrape_latimes(keyword)
    return jsonify({
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "keyword": keyword,
        "url": url,
        "summary": summary
    })

@app.route('/', methods=['GET'])
def index():
    return jsonify({"registration": REGISTRATION, "status": "LA Times Scraper Finalized"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=False)
