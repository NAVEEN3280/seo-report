from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import validators

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
    images_without_alt = [img['src'] for img in images if not img.get('alt')]
    return {"total_images": len(images), "missing_alt": images_without_alt}

def get_links(soup, base_url):
    internal_links = []
    external_links = []
    broken_links = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        link = urljoin(base_url, href)
        if link.startswith(base_url):
            internal_links.append(link)
        else:
            external_links.append(link)

        try:
            response = requests.head(link, timeout=5)
            if response.status_code >= 400:
                broken_links.append(link)
        except requests.RequestException:
            broken_links.append(link)
    
    return {"internal_links": internal_links, "external_links": external_links, "broken_links": broken_links}

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
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        return render_template('index.html', error=f"Failed to analyze the URL: {e}")

    metadata = get_metadata(soup)
    headers = get_headers(soup)
    images = get_images(soup)
    links = get_links(soup, url)
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
