#!/usr/bin/env python3
"""
Blog Content Pipeline (Python rewrite of the n8n workflow).

Flow:
  1. Fetch Hacker News front-page stories (Algolia API, no auth needed).
  2. Pick one story at random.
  3. Ask Google Gemini to draft an original blog post inspired by that topic,
     returned as structured JSON (slug/title/description/body).
  4. Write it as an Astro content-collection markdown file matching
     src/content/config.ts's schema (title, description, pubDate, ...).

Env vars required:
  GEMINI_API_KEY   - Google Gemini API key (repo secret in GitHub Actions)

Optional env vars:
  GEMINI_MODEL     - defaults to "gemini-2.5-flash"
  CONTENT_DIR      - defaults to "src/content/blog"
  HN_POOL_SIZE     - how many front-page stories to sample from (default 30)
"""

import json
import os
import random
import re
import sys
import urllib.request
from datetime import date

HN_FRONT_PAGE_URL = "https://hn.algolia.com/api/v1/search?tags=front_page"

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CONTENT_DIR = os.environ.get("CONTENT_DIR", "src/content/blog")
HN_POOL_SIZE = int(os.environ.get("HN_POOL_SIZE", "30"))


def http_json(url, data=None, headers=None, method=None):
    headers = headers or {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = "<no response body>"
        raise RuntimeError(
            f"HTTP {e.code} from {url}\nResponse body: {error_body}"
        ) from None


def fetch_hn_topic():
    result = http_json(HN_FRONT_PAGE_URL)
    hits = result.get("hits", [])
    if not hits:
        raise RuntimeError("No Hacker News front-page stories returned")
    pool = hits[:HN_POOL_SIZE] if HN_POOL_SIZE else hits
    story = random.choice(pool)
    return {
        "title": story.get("title", "").strip(),
        "url": story.get("url") or f"https://news.ycombinator.com/item?id={story.get('objectID')}",
        "points": story.get("points"),
    }


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:80]


def draft_post(topic):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    gemini_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    system_prompt = (
        "You are a technical blogger writing original, engaging posts for a "
        "developer-focused tech blog. Respond with ONLY a JSON object, no "
        "markdown fences, no commentary. The JSON object must have exactly "
        "these keys: slug (kebab-case, no more than 8 words), title, "
        "description (max 160 chars, for SEO), body (the full post in "
        "Markdown, 500-900 words, with headings, no frontmatter, no h1 "
        "since the title is rendered separately)."
    )
    user_prompt = (
        f"Write an original blog post inspired by this trending story:\n\n"
        f"Title: {topic['title']}\n"
        f"Source: {topic['url']}\n\n"
        "Don't just summarize the article — riff on the underlying idea, "
        "connect it to something a working developer would find useful or "
        "interesting."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.8,
            "responseMimeType": "application/json"
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    result = http_json(gemini_url, data=payload, headers=headers, method="POST")
    
    # Extract the response text from Gemini's payload format
    try:
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        post = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to parse response from Gemini API: {e}")

    for key in ("slug", "title", "description", "body"):
        if not post.get(key):
            raise RuntimeError(f"Model response missing required field: {key}")

    post["slug"] = slugify(post["slug"])
    return post


def build_markdown(post):
    pub_date = date.today().isoformat()
    # Escape any stray double quotes in frontmatter strings.
    title = post["title"].replace('"', '\\"')
    description = post["description"].replace('"', '\\"')
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f'description: "{description}"\n'
        f"pubDate: {pub_date}\n"
        "---\n\n"
    )
    return frontmatter + post["body"].strip() + "\n"


def unique_filepath(content_dir, slug):
    path = os.path.join(content_dir, f"{slug}.md")
    if not os.path.exists(path):
        return path
    return os.path.join(content_dir, f"{slug}-{date.today().isoformat()}.md")


def main():
    topic = fetch_hn_topic()
    print(f"Selected HN topic: {topic['title']}", file=sys.stderr)

    post = draft_post(topic)
    markdown = build_markdown(post)

    os.makedirs(CONTENT_DIR, exist_ok=True)
    filepath = unique_filepath(CONTENT_DIR, post["slug"])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Wrote {filepath}", file=sys.stderr)
    # Emit the path on stdout so the workflow can use it in the commit message.
    print(filepath)


if __name__ == "__main__":
    main()
