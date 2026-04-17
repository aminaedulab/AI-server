from app.services.content_service import TOPIC_LEVELS, TOPIC_URLS
from app.services.ml_service import estimate_knowledge_state

# For each topic, what are the prerequisite topics a student should know first
TOPIC_PREREQUISITES = {
    "variables":             ["introduction"],
    "control-flow":          ["variables"],
    "loops":                 ["control-flow"],
    "functions":             ["variables", "control-flow"],
    "expressions-operators": ["variables"],
    "numbers-strings":       ["variables"],
    "arrays":                ["variables", "loops"],
    "objects":               ["variables", "functions"],
    "classes":               ["objects", "functions"],
    "promises":              ["functions", "async-await"],
    "async-await":           ["functions", "promises"],
    "events":                ["functions", "objects"],
    "error-handling":        ["control-flow", "functions"],
    "regular-expressions":   ["numbers-strings"],
    "keyed-collections":     ["objects", "arrays"],
    "indexed-collections":   ["arrays"],
    "dates":                 ["objects"],
    "modules":               ["functions", "objects"],
    "closures":              ["functions", "variables"],
    "prototypes":            ["objects", "classes"],
    "iterators-generators":  ["loops", "functions", "closures"],
    "typed-arrays":          ["arrays", "indexed-collections"],
    "memory-management":     ["closures", "prototypes"],
    "equality-comparisons":  ["variables", "expressions-operators"],
    "data-structures":       ["arrays", "objects", "keyed-collections"],
    "meta-programming":      ["closures", "prototypes", "classes"],
    "internationalization":  ["objects", "dates"],
}

# Human-readable labels
TOPIC_LABELS = {
    "introduction":          "Introduction to JavaScript",
    "variables":             "Variables & Data Types",
    "control-flow":          "Control Flow & Error Handling",
    "loops":                 "Loops & Iteration",
    "functions":             "Functions",
    "expressions-operators": "Expressions & Operators",
    "numbers-strings":       "Numbers & Strings",
    "arrays":                "Arrays",
    "objects":               "Working with Objects",
    "classes":               "Classes",
    "promises":              "Promises",
    "async-await":           "Async / Await",
    "events":                "Events",
    "error-handling":        "Error Handling",
    "regular-expressions":   "Regular Expressions",
    "keyed-collections":     "Map, Set & Keyed Collections",
    "indexed-collections":   "Indexed Collections",
    "dates":                 "Dates & Times",
    "modules":               "JavaScript Modules",
    "closures":              "Closures",
    "prototypes":            "Prototypes & Inheritance",
    "iterators-generators":  "Iterators & Generators",
    "typed-arrays":          "Typed Arrays",
    "memory-management":     "Memory Management",
    "equality-comparisons":  "Equality & Comparisons",
    "data-structures":       "Data Structures",
    "meta-programming":      "Meta Programming",
    "internationalization":  "Internationalization",
}


def get_topic_level(topic: str) -> str:
    for level, topics in TOPIC_LEVELS.items():
        if topic in topics:
            return level
    return "unknown"


def evaluate_quiz(topic: str, answers: list) -> dict:
    """
    answers: list of {
        "question": str,
        "correctAnswer": str,       # correct label e.g. "B"
        "correctAnswerText": str,   # correct answer text
        "studentAnswer": str,       # what student picked e.g. "A"
        "studentAnswerText": str    # optional text of what they picked
    }

    Returns evaluation with score, feedback per question,
    improvement suggestions, and recommended next lessons.
    """
    total = len(answers)
    if total == 0:
        return {"error": "No answers provided"}

    correct_count = 0
    wrong_questions = []

    for ans in answers:
        is_correct = ans.get("studentAnswer", "").upper() == ans.get("correctAnswer", "").upper()
        if is_correct:
            correct_count += 1
        else:
            wrong_questions.append({
                "question":          ans.get("question"),
                "yourAnswer":        ans.get("studentAnswerText") or ans.get("studentAnswer"),
                "correctAnswer":     ans.get("correctAnswerText") or ans.get("correctAnswer"),
            })

    score_pct = round((correct_count / total) * 100)
    level = get_topic_level(topic)

    # --- Performance band ---
    if score_pct >= 80:
        performance = "excellent"
        summary = f"Great job! You scored {score_pct}% on {TOPIC_LABELS.get(topic, topic)}."
    elif score_pct >= 60:
        performance = "good"
        summary = f"Good effort. You scored {score_pct}% — a bit more practice will solidify this topic."
    elif score_pct >= 40:
        performance = "needs_improvement"
        summary = f"You scored {score_pct}%. You have a basic understanding but need to revisit key concepts."
    else:
        performance = "struggling"
        summary = f"You scored {score_pct}%. It looks like this topic needs more attention before moving on."

    # --- Improvement suggestions ---
    suggestions = build_suggestions(topic, performance, wrong_questions)

    # --- Recommended lessons ---
    recommended = build_recommendations(topic, performance, level)

    return {
        "topic":           topic,
        "topicLabel":      TOPIC_LABELS.get(topic, topic),
        "score":           score_pct,
        "correct":         correct_count,
        "total":           total,
        "performance":     performance,
        "summary":         summary,
        "wrongAnswers":    wrong_questions,
        "suggestions":     suggestions,
        "recommended":     recommended,
        "knowledgeState":  estimate_knowledge_state([{"accuracy": score_pct, "topic": topic}]),
    }


def build_suggestions(topic: str, performance: str, wrong_questions: list) -> list:
    suggestions = []

    if performance == "excellent":
        suggestions.append("You have a strong grasp of this topic. Try the next level to keep progressing.")
        suggestions.append("Challenge yourself by exploring edge cases and advanced patterns.")
        return suggestions

    if performance in ("struggling", "needs_improvement"):
        suggestions.append(
            f"Re-read the {TOPIC_LABELS.get(topic, topic)} guide on MDN: "
            f"{TOPIC_URLS.get(topic, 'https://developer.mozilla.org/en-US/docs/Web/JavaScript')}"
        )

    if wrong_questions:
        suggestions.append(
            f"You got {len(wrong_questions)} question(s) wrong. "
            "Review the specific concepts behind those questions before retaking the quiz."
        )

    prereqs = TOPIC_PREREQUISITES.get(topic, [])
    if prereqs and performance in ("struggling", "needs_improvement"):
        prereq_labels = [TOPIC_LABELS.get(p, p) for p in prereqs]
        suggestions.append(
            f"Make sure you're solid on the prerequisites: {', '.join(prereq_labels)}."
        )

    if performance == "good":
        suggestions.append("Try retaking the quiz to push your score above 80%.")

    return suggestions


def build_recommendations(topic: str, performance: str, level: str) -> list:
    all_topics = (
        TOPIC_LEVELS["beginner"] +
        TOPIC_LEVELS["intermediate"] +
        TOPIC_LEVELS["advanced"]
    )
    topic_index = all_topics.index(topic) if topic in all_topics else -1
    recommendations = []

    if performance in ("struggling", "needs_improvement"):
        # Recommend prerequisites first
        prereqs = TOPIC_PREREQUISITES.get(topic, [])
        for p in prereqs[:2]:
            recommendations.append({
                "topic":  p,
                "label":  TOPIC_LABELS.get(p, p),
                "reason": "Prerequisite — strengthen this foundation first",
                "url":    TOPIC_URLS.get(p)
            })
        # Also recommend retrying current topic
        recommendations.append({
            "topic":  topic,
            "label":  TOPIC_LABELS.get(topic, topic),
            "reason": "Retry this topic after reviewing the material",
            "url":    TOPIC_URLS.get(topic)
        })

    elif performance == "good":
        # Retry current + peek at next
        recommendations.append({
            "topic":  topic,
            "label":  TOPIC_LABELS.get(topic, topic),
            "reason": "Retry to reach 80%+ before moving on",
            "url":    TOPIC_URLS.get(topic)
        })
        if topic_index >= 0 and topic_index + 1 < len(all_topics):
            next_topic = all_topics[topic_index + 1]
            recommendations.append({
                "topic":  next_topic,
                "label":  TOPIC_LABELS.get(next_topic, next_topic),
                "reason": "Up next in the curriculum",
                "url":    TOPIC_URLS.get(next_topic)
            })

    elif performance == "excellent":
        # Recommend next 2 topics
        for i in range(1, 3):
            if topic_index >= 0 and topic_index + i < len(all_topics):
                next_topic = all_topics[topic_index + i]
                recommendations.append({
                    "topic":  next_topic,
                    "label":  TOPIC_LABELS.get(next_topic, next_topic),
                    "reason": "Next lesson in your learning path",
                    "url":    TOPIC_URLS.get(next_topic)
                })

    return recommendations
