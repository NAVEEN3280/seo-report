from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import validators
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Define SEO analysis functions
def get_metadata(soup):
    title = soup.title.string if soup.title else None
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    description = meta_desc['content'] if meta_desc else None
    return {"title": title, "description": description}

def get_headers(soup):
    headers = {}
    for i in range(1, 7):
        headers[f'h{i}'] = [tag.get_text(strip=True) for tag in soup.find_all(f'h{i}')]
    return headers

def get_images(soup):
    images = soup.find_all('img')
    missing_alt = []
    with ThreadPoolExecutor() as executor:
        for img in images:
            if not img.get('alt'):
                missing_alt.append(img['src'])
    return {"total_images": len(images), "missing_alt": missing_alt}

async def check_link(session, link):
    try:
        async with session.head(link, timeout=5) as response:
            if response.status >= 400:
                return link, 'broken'
            return link, 'valid'
    except:
        return link, 'broken'

async def fetch_links(base_url, links):
    internal_links, external_links, broken_links = [], [], []
    async with aiohttp.ClientSession() as session:
        tasks = [check_link(session, urljoin(base_url, href)) for href in links]
        results = await asyncio.gather(*tasks)
        for href, status in results:
            link = urljoin(base_url, href)
            if link.startswith(base_url):
                internal_links.append(link)
            else:
                external_links.append(link)
            if status == 'broken':
                broken_links.append(link)
    return {"internal_links": internal_links, "external_links": external_links, "broken_links": broken_links}

def get_links(soup, base_url):
    links = [a['href'] for a in soup.find_all('a', href=True)]
    return asyncio.run(fetch_links(base_url, links))

def calculate_seo_score(report):
    score = 10
    improvements = []

    if not report['metadata']['title']:
        score -= 1
        improvements.append("Add a descriptive and concise page title.")
    if not report['metadata']['description']:
        score -= 1
        improvements.append("Provide a meta description to improve click-through rates.")
    if not report['headers']['h1']:
        score -= 1
        improvements.append("Include an H1 tag to improve content hierarchy.")
    if report['images']['missing_alt']:
        score -= 1
        improvements.append(
            f"Add alt text to {len(report['images']['missing_alt'])} image(s) for better accessibility."
        )
    if report['links']['broken_links']:
        score -= 2
        improvements.append(
            f"Fix or remove {len(report['links']['broken_links'])} broken link(s) to enhance user experience."
        )
    
    return max(0, min(score, 10)), improvements


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/seo_report', methods=['POST'])
def seo_report():
    url = request.form['url']
    if not validators.url(url):
        return render_template('index.html', error="Invalid URL, please try again.")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')  # Using lxml for faster parsing
    except requests.RequestException as e:
        return render_template('index.html', error=f"Failed to analyze the URL: {e}")

    # Optimize analysis by threading and async tasks
    with ThreadPoolExecutor() as executor:
        metadata_future = executor.submit(get_metadata, soup)
        headers_future = executor.submit(get_headers, soup)
        images_future = executor.submit(get_images, soup)
        links = get_links(soup, url)  # Concurrent link analysis

    metadata = metadata_future.result()
    headers = headers_future.result()
    images = images_future.result()
    report = {
        "metadata": metadata,
        "headers": headers,
        "images": images,
        "links": links,
    }
    score, improvements = calculate_seo_score(report)

    # Render the report on the new page with improvements
    return render_template('report.html', seo_report=report, score=score, url=url, improvements=improvements)

if __name__ == "__main__":
    app.run(debug=True)
