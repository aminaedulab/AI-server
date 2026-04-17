"""
Explain Service — provides concept explanations and code examples for topics.
Uses MDN content + T5 summarization to give targeted explanations.
"""

import re
import logging
from app.services.content_service import fetch_topic_content, TOPIC_LABELS, TOPIC_URLS
from app.services.ml_service import summarize_text_t5

logger = logging.getLogger(__name__)

# Curated code examples per topic — these are the most important ones for understanding
CODE_EXAMPLES = {
    "variables": [
        {
            "title": "var vs let vs const",
            "code": "var x = 1;   // function-scoped, can re-declare\nlet y = 2;   // block-scoped, can reassign\nconst z = 3; // block-scoped, cannot reassign\n\nif (true) {\n  let blockVar = 'only here';\n  var funcVar  = 'everywhere in function';\n}\n// console.log(blockVar); // ReferenceError\nconsole.log(funcVar); // works",
            "explanation": "var is function-scoped and hoisted. let and const are block-scoped. Prefer const by default, use let when you need to reassign."
        },
        {
            "title": "Destructuring",
            "code": "const person = { name: 'Alice', age: 25 };\nconst { name, age } = person;\n\nconst nums = [1, 2, 3];\nconst [first, second] = nums;\n\nconsole.log(name, age, first, second);",
            "explanation": "Destructuring lets you unpack values from objects and arrays into variables in one line."
        }
    ],
    "functions": [
        {
            "title": "Function declaration vs arrow function",
            "code": "// Declaration — hoisted\nfunction greet(name) {\n  return `Hello, ${name}`;\n}\n\n// Arrow — not hoisted, no own 'this'\nconst greetArrow = (name) => `Hello, ${name}`;\n\n// Default parameters\nconst add = (a, b = 0) => a + b;\nconsole.log(add(5)); // 5",
            "explanation": "Arrow functions are shorter and don't bind their own 'this', making them ideal for callbacks. Use function declarations when you need hoisting or a named function."
        },
        {
            "title": "Higher-order functions",
            "code": "const numbers = [1, 2, 3, 4, 5];\n\nconst doubled  = numbers.map(n => n * 2);\nconst evens    = numbers.filter(n => n % 2 === 0);\nconst sum      = numbers.reduce((acc, n) => acc + n, 0);\n\nconsole.log(doubled); // [2,4,6,8,10]\nconsole.log(evens);   // [2,4]\nconsole.log(sum);     // 15",
            "explanation": "map, filter, and reduce are the core higher-order functions. They take a function as an argument and return a new value without mutating the original array."
        }
    ],
    "closures": [
        {
            "title": "Closure basics",
            "code": "function makeCounter() {\n  let count = 0;          // private variable\n  return function() {\n    count++;\n    return count;\n  };\n}\n\nconst counter = makeCounter();\nconsole.log(counter()); // 1\nconsole.log(counter()); // 2\nconsole.log(counter()); // 3",
            "explanation": "A closure is a function that remembers the variables from its outer scope even after the outer function has returned. Here count is private — only accessible through the returned function."
        }
    ],
    "promises": [
        {
            "title": "Promise chain",
            "code": "fetch('https://api.example.com/data')\n  .then(response => response.json())\n  .then(data => console.log(data))\n  .catch(error => console.error('Failed:', error))\n  .finally(() => console.log('Done'));",
            "explanation": "Promises represent a future value. .then() handles success, .catch() handles errors, .finally() always runs. Each .then() returns a new Promise, enabling chaining."
        }
    ],
    "async-await": [
        {
            "title": "async/await vs Promise chain",
            "code": "// Same logic, cleaner syntax\nasync function loadUser(id) {\n  try {\n    const response = await fetch(`/api/users/${id}`);\n    const user = await response.json();\n    return user;\n  } catch (error) {\n    console.error('Error:', error);\n  }\n}\n\n// Parallel requests\nasync function loadAll() {\n  const [users, posts] = await Promise.all([\n    fetch('/api/users').then(r => r.json()),\n    fetch('/api/posts').then(r => r.json()),\n  ]);\n  console.log(users, posts);\n}",
            "explanation": "async/await is syntactic sugar over Promises. await pauses execution until the Promise resolves. Use Promise.all() to run multiple async operations in parallel."
        }
    ],
    "classes": [
        {
            "title": "Class with inheritance",
            "code": "class Animal {\n  constructor(name) {\n    this.name = name;\n  }\n  speak() {\n    return `${this.name} makes a sound.`;\n  }\n}\n\nclass Dog extends Animal {\n  speak() {\n    return `${this.name} barks.`;\n  }\n}\n\nconst d = new Dog('Rex');\nconsole.log(d.speak()); // Rex barks.\nconsole.log(d instanceof Animal); // true",
            "explanation": "Classes are syntactic sugar over prototypes. extends sets up inheritance. super() calls the parent constructor. Always call super() before using 'this' in a subclass."
        }
    ],
    "arrays": [
        {
            "title": "Array methods chaining",
            "code": "const students = [\n  { name: 'Alice', score: 85 },\n  { name: 'Bob',   score: 42 },\n  { name: 'Carol', score: 91 },\n];\n\nconst topStudents = students\n  .filter(s => s.score >= 80)\n  .map(s => s.name)\n  .sort();\n\nconsole.log(topStudents); // ['Alice', 'Carol']",
            "explanation": "Array methods can be chained because each returns a new array. filter → map → sort is a common pattern for transforming data."
        }
    ],
    "objects": [
        {
            "title": "Object spread and shorthand",
            "code": "const name = 'Alice';\nconst age  = 25;\n\n// Shorthand property names\nconst person = { name, age };\n\n// Spread — shallow copy + override\nconst updated = { ...person, age: 26 };\n\n// Optional chaining\nconst city = person?.address?.city ?? 'Unknown';\nconsole.log(city); // 'Unknown'",
            "explanation": "Spread (...) creates a shallow copy. Optional chaining (?.) safely accesses nested properties without throwing if a value is null/undefined. Nullish coalescing (??) provides a default."
        }
    ],
    "loops": [
        {
            "title": "for...of vs for...in",
            "code": "const arr = ['a', 'b', 'c'];\n\n// for...of — iterates VALUES (use for arrays)\nfor (const val of arr) {\n  console.log(val); // 'a', 'b', 'c'\n}\n\n// for...in — iterates KEYS (use for objects)\nconst obj = { x: 1, y: 2 };\nfor (const key in obj) {\n  console.log(key, obj[key]); // 'x' 1, 'y' 2\n}",
            "explanation": "for...of iterates over iterable values (arrays, strings, Maps). for...in iterates over enumerable property keys of an object. Don't use for...in on arrays."
        }
    ],
    "control-flow": [
        {
            "title": "switch and ternary",
            "code": "// switch — cleaner than many if/else\nconst day = 'Monday';\nswitch (day) {\n  case 'Monday':\n  case 'Tuesday':\n    console.log('Weekday');\n    break;\n  default:\n    console.log('Other');\n}\n\n// Ternary — inline if/else\nconst score = 75;\nconst grade = score >= 90 ? 'A' : score >= 70 ? 'B' : 'C';\nconsole.log(grade); // 'B'",
            "explanation": "switch is cleaner than long if/else chains when comparing one value against many cases. Ternary is great for simple inline conditions but avoid nesting them deeply."
        }
    ],
    "error-handling": [
        {
            "title": "try/catch/finally",
            "code": "async function fetchData(url) {\n  try {\n    const res = await fetch(url);\n    if (!res.ok) throw new Error(`HTTP ${res.status}`);\n    return await res.json();\n  } catch (err) {\n    if (err instanceof TypeError) {\n      console.error('Network error:', err.message);\n    } else {\n      console.error('API error:', err.message);\n    }\n    return null;\n  } finally {\n    console.log('Request complete');\n  }\n}",
            "explanation": "Always check res.ok before parsing JSON. Use instanceof to handle different error types differently. finally runs whether or not an error occurred — good for cleanup."
        }
    ],
    "modules": [
        {
            "title": "ES Modules",
            "code": "// math.js\nexport const PI = 3.14159;\nexport function add(a, b) { return a + b; }\nexport default function multiply(a, b) { return a * b; }\n\n// main.js\nimport multiply, { PI, add } from './math.js';\nimport * as math from './math.js';\n\nconsole.log(PI);          // 3.14159\nconsole.log(add(2, 3));   // 5\nconsole.log(multiply(4, 5)); // 20",
            "explanation": "Named exports use { } on import. Default exports don't. import * as brings everything under a namespace. ES modules are static — imports are resolved at parse time, not runtime."
        }
    ],
}


def get_code_examples(topic: str) -> list:
    """Return curated code examples for a topic."""
    return CODE_EXAMPLES.get(topic, [])


def explain_concept(topic: str, question: str) -> dict:
    """
    Generate a targeted explanation for a student's question about a topic.
    Uses MDN content + extractive matching to find the most relevant paragraph.
    Falls back to a general summary if no match found.
    """
    try:
        raw_text = fetch_topic_content(topic)
    except Exception:
        raw_text = ""

    explanation = ""
    source = "fallback"

    if raw_text and question:
        # Find the most relevant paragraph using keyword overlap
        q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
        sentences = [s.strip() for s in raw_text.split(". ") if len(s.strip()) > 60]

        best_score = 0
        best_sent = ""
        for sent in sentences:
            s_words = set(re.findall(r'\b\w{4,}\b', sent.lower()))
            overlap = len(q_words & s_words)
            if overlap > best_score:
                best_score = overlap
                best_sent = sent

        if best_score >= 2 and best_sent:
            # Take the matching sentence + 2 surrounding sentences for context
            idx = sentences.index(best_sent)
            context = sentences[max(0, idx-1): idx+3]
            explanation = ". ".join(context) + "."
            source = "mdn_extract"

    # If no good match, use T5 summary of the whole topic
    if not explanation:
        summary = summarize_text_t5(raw_text[:2000], max_length=150) if raw_text else None
        if summary:
            explanation = summary
            source = "t5_summary"
        else:
            explanation = (
                f"This concept is part of {TOPIC_LABELS.get(topic, topic)}. "
                f"Read the full MDN guide: {TOPIC_URLS.get(topic, 'https://developer.mozilla.org/en-US/docs/Web/JavaScript')}"
            )

    return {
        "topic": topic,
        "question": question,
        "explanation": explanation,
        "source": source,
        "mdnUrl": TOPIC_URLS.get(topic, "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
        "codeExamples": get_code_examples(topic)[:1],  # return 1 relevant example
    }
