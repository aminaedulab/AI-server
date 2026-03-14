import random
import re

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', '', text).lower()

def generate_wrong_options(correct, keywords):
    options = set()
    for word in keywords:
        if word not in correct.lower() and len(word) > 4:
            options.add(word.capitalize())
    while len(options) < 3:
        options.add("Not related")
    return list(options)[:3]

def generate_quiz(lesson_text):
    sentences = lesson_text.split(".")
    questions = []
    keywords = clean_text(lesson_text).split()

    for sentence in sentences:
        sentence = sentence.strip()
        lower = sentence.lower()

        if " is " in lower:
            parts = sentence.split(" is ")
            subject = parts[0].strip()
            answer = parts[1].strip()

            question = f"What is {subject}?"
        
        elif " is used to " in lower:
            parts = sentence.split(" is used to ")
            subject = parts[0].strip()
            answer = parts[1].strip()

            question = f"What is {subject} used for?"

        elif " store " in lower or " stores " in lower:
            parts = sentence.split(" store ")
            subject = parts[0].strip()
            answer = parts[-1].strip()

            question = f"What does {subject} store?"

        else:
            continue

        wrong_options = generate_wrong_options(answer, keywords)
        options = wrong_options + [answer]
        random.shuffle(options)

        questions.append({
            "question": question,
            "options": options,
            "correctAnswer": answer
        })

    return questions[:5]
