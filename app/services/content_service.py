import re
import requests
from bs4 import BeautifulSoup

MDN_BASE = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"
MDN_LEARN = "https://developer.mozilla.org/en-US/docs/Learn/JavaScript"
MDN_REF   = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects"

TOPIC_URLS = {
    "introduction":             f"{MDN_BASE}/Introduction",
    "variables":                f"{MDN_BASE}/Grammar_and_types",
    "control-flow":             f"{MDN_BASE}/Control_flow_and_error_handling",
    "loops":                    f"{MDN_BASE}/Loops_and_iteration",
    "functions":                f"{MDN_BASE}/Functions",
    "expressions-operators":    f"{MDN_BASE}/Expressions_and_operators",
    "numbers-strings":          f"{MDN_BASE}/Numbers_and_strings",
    "arrays":                   f"{MDN_REF}/Array",
    "objects":                  f"{MDN_BASE}/Working_with_objects",
    "classes":                  f"{MDN_BASE}/Using_classes",
    "promises":                 f"{MDN_BASE}/Using_promises",
    "async-await":              "https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Asynchronous/Promises",
    "events":                   "https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Building_blocks/Events",
    "error-handling":           "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Control_flow_and_error_handling",
    "regular-expressions":      f"{MDN_BASE}/Regular_expressions",
    "keyed-collections":        f"{MDN_BASE}/Keyed_collections",
    "indexed-collections":      f"{MDN_BASE}/Indexed_collections",
    "dates":                    f"{MDN_BASE}/Representing_dates_times",
    "modules":                  f"{MDN_BASE}/JavaScript_modules",
    "closures":                 "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Closures",
    "prototypes":               "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Inheritance_and_the_prototype_chain",
    "iterators-generators":     f"{MDN_BASE}/Iterators_and_generators",
    "typed-arrays":             f"{MDN_BASE}/Typed_arrays",
    "memory-management":        "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Memory_management",
    "equality-comparisons":     "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Equality_comparisons_and_sameness",
    "data-structures":          "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Data_structures",
    "meta-programming":         f"{MDN_BASE}/Meta_programming",
    "internationalization":     f"{MDN_BASE}/Internationalization",
}

TOPIC_LEVELS = {
    "beginner":     ["introduction", "variables", "control-flow", "loops", "functions",
                     "expressions-operators", "numbers-strings", "arrays", "objects"],
    "intermediate": ["classes", "promises", "async-await", "events", "error-handling",
                     "regular-expressions", "keyed-collections", "indexed-collections",
                     "dates", "modules"],
    "advanced":     ["closures", "prototypes", "iterators-generators", "typed-arrays",
                     "memory-management", "equality-comparisons", "data-structures",
                     "meta-programming", "internationalization"],
}

TOPIC_LABELS = {
    "introduction": "Introduction to JavaScript",
    "variables": "Variables & Data Types",
    "control-flow": "Control Flow",
    "loops": "Loops & Iteration",
    "functions": "Functions",
    "expressions-operators": "Expressions & Operators",
    "numbers-strings": "Numbers & Strings",
    "arrays": "Arrays",
    "objects": "Working with Objects",
    "classes": "Classes",
    "promises": "Promises",
    "async-await": "Async / Await",
    "events": "Events",
    "error-handling": "Error Handling",
    "regular-expressions": "Regular Expressions",
    "keyed-collections": "Map, Set & Keyed Collections",
    "indexed-collections": "Indexed Collections",
    "dates": "Dates & Times",
    "modules": "JavaScript Modules",
    "closures": "Closures",
    "prototypes": "Prototypes & Inheritance",
    "iterators-generators": "Iterators & Generators",
    "typed-arrays": "Typed Arrays",
    "memory-management": "Memory Management",
    "equality-comparisons": "Equality & Comparisons",
    "data-structures": "Data Structures",
    "meta-programming": "Meta Programming",
    "internationalization": "Internationalization",
}


def _get_soup(topic: str):
    """Fetch MDN page and return BeautifulSoup object."""
    topic = topic.lower().strip()
    url = TOPIC_URLS.get(topic)
    if not url:
        url = f"{MDN_BASE}/{topic.replace(' ', '_').title()}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser"), url


def fetch_topic_content(topic: str) -> str:
    """
    Fetch plain text from MDN (paragraphs only).
    Used for quiz generation and AI summarization input.
    """
    soup, _ = _get_soup(topic)
    article = soup.find("article") or soup.find(class_="main-page-content") or soup.find("main")
    if not article:
        raise ValueError("Could not parse page content.")

    for tag in article.find_all(["code", "pre", "nav", "aside", "button", "figure", "table"]):
        tag.decompose()

    paragraphs = article.find_all("p")
    text = " ".join(p.get_text(separator=" ").strip() for p in paragraphs if len(p.get_text()) > 40)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\[[\w\s]+\]', '', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text.strip()


def fetch_rich_content(topic: str) -> dict:
    """
    Fetch structured content from MDN — preserves headings, paragraphs, and
    inline code snippets. Returns a dict with:
      - title: str
      - intro: str  (first 2-3 paragraphs)
      - sections: list of { heading: str, body: str, codeSnippets: list[str] }
      - keyPoints: list[str]  (bullet-style sentences extracted from the text)
      - mdnUrl: str
    """
    soup, url = _get_soup(topic)
    article = soup.find("article") or soup.find(class_="main-page-content") or soup.find("main")
    if not article:
        raise ValueError("Could not parse page content.")

    # Remove nav/aside/buttons but KEEP pre/code for snippets
    for tag in article.find_all(["nav", "aside", "button", "figure"]):
        tag.decompose()

    title = TOPIC_LABELS.get(topic, topic.replace("-", " ").title())

    # ── Extract intro (first paragraphs before any h2/h3) ──────────────────
    intro_parts = []
    for el in article.children:
        if not hasattr(el, 'name'):
            continue
        if el.name in ("h2", "h3"):
            break
        if el.name == "p":
            t = _clean(el.get_text())
            if len(t) > 50:
                intro_parts.append(t)
        if len(intro_parts) >= 3:
            break
    intro = " ".join(intro_parts)

    # ── Extract sections under each h2/h3 ──────────────────────────────────
    sections = []
    current_heading = None
    current_body = []
    current_code = []

    for el in article.find_all(["h2", "h3", "p", "pre", "ul", "ol"]):
        if el.name in ("h2", "h3"):
            if current_heading and (current_body or current_code):
                body_text = " ".join(current_body)
                if len(body_text) > 60:
                    sections.append({
                        "heading": current_heading,
                        "body": body_text,
                        "codeSnippets": current_code[:2],  # max 2 snippets per section
                    })
            current_heading = _clean(el.get_text())
            current_body = []
            current_code = []

        elif el.name == "p":
            t = _clean(el.get_text())
            if len(t) > 40:
                current_body.append(t)

        elif el.name == "pre":
            code = el.get_text().strip()
            if code and len(code) > 10:
                current_code.append(code[:600])  # cap snippet length

        elif el.name in ("ul", "ol"):
            items = [_clean(li.get_text()) for li in el.find_all("li") if len(li.get_text()) > 15]
            if items:
                current_body.append("• " + "\n• ".join(items[:8]))

    # flush last section
    if current_heading and current_body:
        sections.append({
            "heading": current_heading,
            "body": " ".join(current_body),
            "codeSnippets": current_code[:2],
        })

    # ── Key points: sentences that contain "is", "are", "means", "allows" ──
    all_text = intro + " " + " ".join(s["body"] for s in sections)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', all_text) if len(s.strip()) > 50]
    key_words = {"is", "are", "means", "allows", "enables", "defines", "returns", "creates"}
    key_points = [
        s for s in sentences
        if any(f" {kw} " in s.lower() for kw in key_words)
    ][:8]

    return {
        "title": title,
        "intro": intro,
        "sections": sections[:8],   # cap at 8 sections
        "keyPoints": key_points,
        "mdnUrl": url,
        "topic": topic,
    }


def _clean(text: str) -> str:
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\[[\w\s]+\]', '', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text.strip()


def get_available_topics() -> dict:
    return TOPIC_LEVELS
