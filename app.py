import time
import streamlit as st
import random
from groq import Groq
import os
import json

import sqlite3

conn = sqlite3.connect("leaderboard.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    score INTEGER
)
""")
conn.commit()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.title("🎮 Adaptive AI Quiz Game (Offline v2)")

# --- Session State Initialization ---
if "start_time" not in st.session_state:
    st.session_state.start_time = None

if "level" not in st.session_state:
    st.session_state.level = 1

if "xp" not in st.session_state:
    st.session_state.xp = 0

if "high_score" not in st.session_state:
    st.session_state.high_score = 0

if "streak" not in st.session_state:
    st.session_state.streak = 0

if "answer_submitted" not in st.session_state:
    st.session_state.answer_submitted = False

if "correct_count" not in st.session_state:
    st.session_state.correct_count = 0

if "wrong_count" not in st.session_state:
    st.session_state.wrong_count = 0

if "round_question" not in st.session_state:
    st.session_state.round_question = None

if "round_options" not in st.session_state:
    st.session_state.round_options = None

if "round_answer" not in st.session_state:
    st.session_state.round_answer = None

if "round_explanation" not in st.session_state:
    st.session_state.round_explanation = None

if "questions_answered_this_level" not in st.session_state:
    st.session_state.questions_answered_this_level = 0

if st.session_state.level > 3:
    st.session_state.level = 3

if "total_correct" not in st.session_state:
    st.session_state.total_correct = 0

if "total_questions" not in st.session_state:
    st.session_state.total_questions = 0

if "question_id" not in st.session_state:
    st.session_state.question_id = 0

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

h3 {
    margin-bottom: 0.5rem;
}

div[data-testid="stMetric"] {
    background-color: #111827;
    padding: 10px;
    border-radius: 10px;
}

div[data-testid="stProgress"] > div > div > div {
    background-color: #22c55e;
}
</style>
""", unsafe_allow_html=True)

st.divider()

def difficulty_badge(level):
    if level == 1:
        return "🟢 Easy"
    elif level == 2:
        return "🟡 Medium"
    else:
        return "🔴 Hard"

def generate_question(topic, level):

    difficulty_map = {
        1: "easy",
        2: "medium",
        3: "hard"
    }

    prompt = f"""
    Generate ONE {difficulty_map[level]} multiple choice question about {topic}.
    
    Requirements:
    - 4 answer choices
    - Only 1 correct answer
    - Plausible distractors
    - Return strictly valid JSON
    
    Format:
    {{
        "question": "...",
        "options": ["A", "B", "C", "D"],
        "answer": "exact correct option text",
        "explanation": "brief explanation of why the answer is correct"
    }}
    """

    with st.spinner("Generating AI question..."):
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an educational quiz generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

    content = response.choices[0].message.content.strip()

    # Remove markdown code blocks if present
    if "```" in content:
        content = content.split("```")[1]

    # Try parsing JSON safely
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        st.error("⚠️ AI returned invalid format. Retrying...")
        return generate_question(topic, level)
    
    return data

# --- UI ---
st.sidebar.title("🏆 Leaderboard")

c.execute("SELECT MAX(score) FROM scores")
top_score = c.fetchone()[0]

if top_score is None:
    top_score = 0

st.sidebar.write(f"Global High Score: {top_score}")

topic = st.text_input("Enter topic:")

st.markdown(f"### Difficulty: {difficulty_badge(st.session_state.level)}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("XP", st.session_state.xp)

with col2:
    st.metric("Streak 🔥", st.session_state.streak)

with col3:
    if st.session_state.total_questions > 0:
        accuracy = st.session_state.total_correct / st.session_state.total_questions
        st.metric("Accuracy", f"{round(accuracy * 100, 1)}%")

st.write(f"Questions this level: {st.session_state.questions_answered_this_level}/3")

xp_progress = min(st.session_state.xp / 200, 1.0)
st.progress(xp_progress)

if st.session_state.total_questions > 0:
    accuracy = (
        st.session_state.total_correct /
        st.session_state.total_questions
    )
    st.metric("Accuracy", f"{round(accuracy * 100, 1)}%")

# --- Mastery Condition ---
if st.session_state.xp >= 200:
    st.success("🏆 You mastered this topic!")
    st.stop()

if topic:

    # Generate question only if none exists
    if st.session_state.round_question is None:
        data = generate_question(topic, st.session_state.level)

        st.session_state.round_question = data["question"]

        options = data["options"]

        labeled_options = [
            f"A. {options[0]}",
            f"B. {options[1]}",
            f"C. {options[2]}",
            f"D. {options[3]}"
        ]

        st.session_state.round_options = labeled_options
        st.session_state.round_answer = next(
            opt for opt in labeled_options if data["answer"] in opt
        )

        st.session_state.round_answer = data["answer"]
        st.session_state.round_explanation = data["explanation"]
        st.session_state.start_time = time.time()

    st.subheader(st.session_state.round_question)

    if st.session_state.start_time and not st.session_state.answer_submitted:
        # 1. Force the app to tick every 1000ms (1 second)
        st_autorefresh(interval=1000, key=f"timer_{st.session_state.question_id}")
        
        elapsed = int(time.time() - st.session_state.start_time)
        remaining = max(15 - elapsed, 0)
        st.write(f"⏱ Time Remaining: {remaining}s")

        # 2. Auto-fail them if the clock hits 0
        if remaining == 0:
            st.warning("Time's up!")
            st.session_state.answer_submitted = True
            st.session_state.last_result = "wrong"
            
            # Apply penalties
            st.session_state.streak = 0
            st.session_state.wrong_count += 1
            st.session_state.questions_answered_this_level += 1
            st.session_state.total_questions += 1
            
            # Force a rerun to immediately lock the radio buttons and show the explanation
            st.rerun()

    radio_key = f"selected_option_{st.session_state.question_id}"

    st.radio(
        "Choose your answer:",
        st.session_state.round_options,
        key=radio_key,
        index=None,
        disabled=st.session_state.answer_submitted
    )

if st.button("Submit Answer") and not st.session_state.answer_submitted:

    selected = st.session_state.get(radio_key)
    elapsed = int(time.time() - st.session_state.start_time)

    if selected is None:
        st.warning("Please select an answer before submitting.")
    else:
        st.session_state.answer_submitted = True

        if selected == st.session_state.round_answer:
            st.session_state.last_result = "correct"
            st.session_state.xp += 10 * st.session_state.level
            st.session_state.streak += 1
            st.session_state.correct_count += 1
            st.session_state.total_correct += 1
        else:
            st.session_state.last_result = "wrong"
            st.session_state.streak = 0
            st.session_state.wrong_count += 1

        if elapsed > 15:
            st.warning("Too slow! The time expired.")
            st.session_state.answer_submitted = True
            st.session_state.last_result = "wrong"
            st.session_state.streak = 0
            st.session_state.wrong_count += 1
            st.session_state.questions_answered_this_level += 1
            st.session_state.total_questions += 1
            st.rerun()

        elif selected is None:
            st.warning("Please select an answer before submitting.")
        else:
            st.session_state.answer_submitted = True
            
        st.session_state.questions_answered_this_level += 1
        st.session_state.total_questions += 1

if st.session_state.answer_submitted:

    if st.session_state.last_result == "correct":
        st.success("Correct! 🎉")
    else:
        st.error(f"Wrong! Correct answer was {st.session_state.round_answer}")

    st.info(f"💡 Explanation: {st.session_state.round_explanation}")

    if st.button("Next Question"):

        # Adaptive logic here (move your level logic here)

        accuracy = (
            st.session_state.total_correct /
            st.session_state.total_questions
            if st.session_state.total_questions > 0 else 0
        )

        if accuracy >= 0.8 and st.session_state.level < 3:
            st.session_state.level += 1
            st.info("🚀 Difficulty Increased!")

        elif accuracy < 0.4 and st.session_state.level > 1:
            st.session_state.level -= 1
            st.warning("📉 Difficulty Decreased")

        # Reset question state
        st.session_state.round_question = None
        st.session_state.answer_submitted = False
        st.session_state.question_id += 1

        st.session_state.start_time = None

        st.rerun()