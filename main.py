# make sure python installed
#set up virtual env:
   # python3 -m venv .venv 
    #source .venv/bin/activate
#install packages:
    #pip install requests beautifulsoup4 openai schedule python-dotenv
#create files:
    #??? .venv/                  # virtual environment
    #??? .env                    # (store your API keys here)
    #??? fitness_blog_bot.py     # (main script)
    #??? README.md               # optional


import os
import sys
import time
import logging
import datetime as dt
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Paths ----------
BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "output"
LOG_DIR = BASE / "logs"
OUT_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR.mkdir(exist_ok=True, parents=True)

# ---------- Logging ----------
LOG_FILE = LOG_DIR / "run.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(console)

# ---------- Env / API ----------
load_dotenv(BASE / ".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY missing in .env")
    sys.exit(1)
client = OpenAI(api_key=OPENAI_API_KEY)

# Optional: enforce timezone for timestamps
tz = os.getenv("TZ", "UTC")
os.environ["TZ"] = tz
try:
    time.tzset()  # works on Linux (Pi)
except AttributeError:
    pass

# ---------- Sources ----------
# Option A) hardcode your 10 sites here:
SITES = [
    "https://www.menshealth.com/fitness/",
    "https://www.t-nation.com/",
    "https://barbend.com/",
    "https://breakingmuscle.com/",
    "https://www.strengthlog.com/",
    "https://muscleandstrength.com/articles",
    "https://examine.com/updates/",
    "https://www.strongerbyscience.com/",
    "https://www.alanaragon.com/blog/",
    "https://www.jtsstrength.com/articles/"
]

# Option B) OR list them in sites.txt (one per line)
sites_txt = BASE / "sites.txt"
if sites_txt.exists():
    with open(sites_txt, "r") as f:
        SITES = [line.strip() for line in f if line.strip()]

# ---------- Helpers ----------
def fetch_text(url, timeout=20):
    logging.info(f"Fetching: {url}")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Grab paragraphs, trim, de-dupe short lines
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n\n".join(p for p in paras if len(p.split()) > 7)
    return text[:15000]  # safety cap

def summarize_to_blog(collected_text, max_words=700):
    system = (
        "You write concise, evidence-aware fitness content for adult readers. "
        "Cite claims cautiously (no made-up citations). Use clear sections and bullet points sparingly."
    )
    user = (
        f"Using the aggregated notes below from several fitness/men's health sites, "
        f"write a single cohesive blog post (~{max_words} words). "
        f"Prioritize actionable training/nutrition takeaways and avoid speculation. "
        f"End with a brief 3–5 item checklist.\n\n=== Notes Start ===\n{collected_text}\n=== Notes End ==="
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()

def write_post(markdown_text):
    today = dt.datetime.now().strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"blog_{today}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    logging.info(f"Wrote blog post: {out_path}")
    return out_path

# ---------- Locking (avoid overlapping runs) ----------
LOCK_FILE = BASE / ".run.lock"

class SingleInstance:
    def __init__(self, lock_path):
        self.lock_path = lock_path
        if self.lock_path.exists():
            raise RuntimeError("Another run is in progress (lock file exists).")
        self.lock_path.write_text(str(os.getpid()))
    def release(self):
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass

def main():
    try:
        lock = SingleInstance(LOCK_FILE)
    except RuntimeError as e:
        logging.warning(str(e))
        return

    try:
        # Aggregate text from all sources
        texts = []
        for url in SITES:
            try:
                texts.append(fetch_text(url))
            except Exception as e:
                logging.error(f"Failed {url}: {e}")

        combined = "\n\n---\n\n".join(t for t in texts if t)
        if not combined.strip():
            logging.error("No content fetched; aborting.")
            return

        blog_md = summarize_to_blog(combined, max_words=750)
        write_post(blog_md)
    except Exception as e:
        logging.exception(f"Run failed: {e}")
    finally:
        lock.release()

if __name__ == "__main__":
    main()