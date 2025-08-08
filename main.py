import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# 1) Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2) Fixed list of sites
URLS = [
    "https://www.menshealth.com/fitness/",
    "https://barbend.com/",
    "https://breakingmuscle.com/",
    "https://www.t-nation.com/",
    "https://www.bodybuilding.com/content",
    "https://www.healthline.com/nutrition",
    "https://www.verywellfit.com/",
    "https://www.mensjournal.com/health-fitness/",
    "https://www.shape.com/fitness",
    "https://www.muscleandstrength.com/workouts"
]

def fetch_text(url):
    """Download page & extract paragraphs."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return "\n\n".join(p.get_text() for p in soup.find_all("p"))
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return ""

def summarize_to_blog(text, max_words=500):
    """Use OpenAI to write a blog-style summary."""
    prompt = (
        f"Write a concise, engaging blog post (≈{max_words} words) based on the following content from multiple sources:\n\n"
        + text
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_words * 4 // 3,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def save_blog(content):
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"blog_post_{today}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Blog post saved to {filename}")

def main():
    print("Fetching content from all sites…")
    combined_text = ""
    for url in URLS:
        print(f"Scraping {url}")
        combined_text += fetch_text(url) + "\n\n"

    print(f"Total extracted words: ~{len(combined_text.split())}")
    blog = summarize_to_blog(combined_text)
    save_blog(blog)

if __name__ == "__main__":
    main()
    