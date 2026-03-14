from transformers import pipeline

question_generator = pipeline("text2text-generation", model="valhalla/t5-small-qg-hl")

def generate_quiz(text):
    text = text[:2000]

    prompt = f"generate questions: {text}"

    output = question_generator(prompt, max_length=150)

    return output[0]["generated_text"]
