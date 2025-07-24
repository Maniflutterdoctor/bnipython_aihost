from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory

from langchain.chains import ConversationChain

import mysql.connector
import re
import json
import unicodedata
from difflib import get_close_matches
from typing import Optional
import os

# FastAPI setup
app = FastAPI()

# Enable CORS for Flutter frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


db_config = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME')
}


# OpenRouter configuration
openrouter_config = {
    'base_url': 'https://api.deepseek.com',
    'api_key': os.environ.get('OPENROUTER_API_KEY'),
    'model': 'deepseek-chat'
}

# Init LLM
llm = ChatOpenAI(
    openai_api_base=openrouter_config['base_url'],
    openai_api_key=openrouter_config['api_key'],
    model_name=openrouter_config['model'],
    temperature=0.2
)

# Memory store per user
user_memory_store = {}





@app.on_event("startup")
async def startup_event():
    try:
        print(">>> Startup event triggered")
        preload_member_names()
        print(">>> Member names preloaded")
    except Exception as e:
        print(f"❌ Error in startup_event: {e}")


def get_conversation_chain(user_id: int):
    if user_id not in user_memory_store:
        memory = ConversationBufferWindowMemory(
            memory_key="history",
            return_messages=True,
            k=3  # ⬅️ This limits to the last 3 exchanges (user+AI)
        )
        chain = ConversationChain(llm=llm, memory=memory)
        user_memory_store[user_id] = chain
    return user_memory_store[user_id]


# Request model
class QuestionRequest(BaseModel):
    question: str
    is_general_knowledge: Optional[bool] = False
    user_id: Optional[int] = None

# Connect DB
def connect_to_database():
    return mysql.connector.connect(**db_config)



# Preload members
member_name_map = {}
def preload_member_names():
    global member_name_map
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, member_name FROM member_details")
        rows = cursor.fetchall()
        conn.close()
        member_name_map = {row['member_name'].strip().lower(): row['id'] for row in rows}
    except Exception as e:
        print(f"[ERROR] Preload failed: {e}")

# Get member info
def get_member_info(member_id: int):
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT member_name, classification, company_name, phone 
            FROM member_details 
            WHERE id = %s
        """, (member_id,))
        member = cursor.fetchone()
        conn.close()
        return member
    except Exception as e:
        print(f"Error fetching member info: {e}")
        return None

# Fuzzy match
def find_closest_member_name(user_input: str):
    input_words = user_input.lower().split()
    names = list(member_name_map.keys())
    for word in input_words:
        matches = get_close_matches(word, names, n=1, cutoff=0.7)
        if matches:
            return matches[0], member_name_map[matches[0]]
    return None

# Normalize output
def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

# BNI Knowledge Base
bni_knowledge = {
    "about": "BNI (Business Network International) is the world's largest business networking organization.",
    "purpose": "BNI's primary purpose is to help members increase their business through referrals.",
    "meetings": "BNI chapters typically meet weekly to exchange qualified business referrals.",
    "givers gain": "The philosophy of BNI is 'Givers Gain' - by giving business to others, you'll get business in return.",
    "membership": "BNI membership is by application and requires a commitment to regular attendance.",
    "founder": "BNI was founded by Dr. Ivan Misner in 1985.",
    "chapters": "BNI has thousands of chapters worldwide across many countries.",
    "mcc": "BNI's Member Connection Committee (MCC) helps new members get oriented.",
    "visitors": "Most BNI chapters allow visitors to attend meetings before joining.",
    "referrals": "The core of BNI is the exchange of quality business referrals between members."
}

def is_general_bni_question(question: str) -> bool:
    question_lower = question.lower()
    bni_keywords = [
        "what is bni", "about bni", "bni purpose", "how does bni work",
        "bni meeting", "bni philosophy", "join bni", "bni founder",
        "bni chapter", "bni referral", "bni membership", "bni benefits"
    ]
    return any(keyword in question_lower for keyword in bni_keywords)

def get_bni_knowledge_response(question: str) -> str:
    question_lower = question.lower()
    for topic, info in bni_knowledge.items():
        if topic in question_lower:
            return info
    prompt = f"""
You are an expert on BNI (Business Network International). 
Provide a helpful, accurate response to this question about BNI.
Keep your answer concise (1-2 paragraphs max).

Question: {question}

BNI Response:
"""
    response = llm.invoke(prompt)
    return response.content.strip()

def personalize_question(question: str, user_id: int) -> str:
    if not user_id:
        return question

    member = get_member_info(user_id)
    if not member:
        return question

    replacements = {
        r'\bmy\b': f"{member['member_name']}'s",
        r'\bme\b': member['member_name'],
        r'\bI\b': member['member_name'],
        r'\bmine\b': f"{member['member_name']}'s"
    }

    for pattern, replacement in replacements.items():
        question = re.sub(pattern, replacement, question, flags=re.IGNORECASE)

    return question

async def generate_query_from_question(question: str, user_id: Optional[int] = None) -> str:
    if user_id:
        question = personalize_question(question, user_id)

    member_schema = """Table: member_details  
Columns: id, member_name, password, classification, company_name, phone, teamname, powerteam, user_type, activestatus"""

    score_schema = """Table: member_scores  
Columns: id, name, powerteam, total_score, referral_score, referral_maintain, referral_recom,
tyftb_score, tyftb_maintain, tyftb_recom, visitor_score, visitor_maintain, visitor_recom,
testimonial_score, testimonial_maintain, testimonial_recom, training_score, training_maintain,
training_recom, absent_score, absent_maintain, absent_recom, arrivingontime_score,
arrivingontime_maintain, arrivingontime_recom"""

    prompt = f"""
You are a SQL generator for a BNI database with two related tables.

{member_schema}

{score_schema}

Details:
- The two tables may be joined using `member_details.member_name = member_scores.name`
- `member_scores` contains weekly score metrics for each member
- `member_details` contains static member info like classification, phone, powerteam, etc.
- 'Team1' Team 1 means BNI Gems members
-  classification is the member's profession or business type
-  member_details tables powerteam  is a group of members with similar professions in example powerteam names BUSINESS SERVICE,BUSINESS OWNERS,CIVIL or civil,CORPORATE,RETAILS
-  the contain user_type only is 'MEMBER' , 'ADMIN','LVH' , 'GUEST-VISITOR','GUEST-SUBSTITUTE' , 'GUEST-OBSERVER',


additional context:
-Members 30 Second Business Presentaion minimum 20 line 
-Members Business Testimonials in best practices minimum 50 line 

Rules:
- Only use SELECT queries
- Use JOIN if question involves both tables
- Never explain the query, just return raw SQL
 the query about Testimonials word find retrive data like this query,
 SELECT * FROM member_details   this table only

User Question: "{question}"
"""
    response = llm.invoke(prompt)
    sql_query = response.content.strip()

    if "```sql" in sql_query:
        sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
    elif "```" in sql_query:
        sql_query = sql_query.split("```")[1].strip()

    print(f"[AI SQL]: {sql_query}")
    return sql_query

def clean_text(text: str) -> str:
    try:
        return text.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError:
        return unicodedata.normalize("NFKC", text)

def generate_friendly_summary(question: str, results: list, user_id: Optional[int] = None) -> str:
    if not results:
        return "Sorry, I couldn't find any matching member based on your question."

    member_info = None
    if user_id:
        member_info = get_member_info(user_id)

    prompt = f"""
You are a friendly AI assistant for BNI members.

The user asked: "{question}"

Here is the data:
{json.dumps(results, indent=2)}

{
    f"Additional context: The user is {member_info['member_name']} from {member_info['company_name']}" 
    if member_info else ""
}

Explain it in a clear, simple, helpful way.

Avoid any database or SQL terms. Just answer naturally and informatively.


Explain it in a clear, simple, helpful way.
Avoid any database or SQL terms. Just answer naturally and informatively.
Add relevant emojis to make the response engaging and fun. 🎯📊😊

"""
    response = llm.invoke(prompt)
    return clean_text(response.content.strip())
    # response = llm.invoke(prompt)
    # summary_text = clean_text(response.content.strip())
    # print("\n[AI general summary Generated]:\n" + "-"*60)
    # print(summary_text)
    # return summary_text



@app.post("/ask")
async def ask_question(data: QuestionRequest):
    question = data.question.strip()
    user_id = data.user_id

    greetings = {
        "hi": "Hi there! 👋",
        "hello": "Hello! 😊",
        "hey": "Hey! ✨",
        "good morning": "Good morning! 🌞",
        "good afternoon": "Good afternoon! ☀️",
        "good evening": "Good evening! 🌙"
    }

    clean_input = re.sub(r'[^\w\s]', '', question.lower())
    if clean_input in greetings:
        greeting = greetings[clean_input]

        if user_id:
            member = get_member_info(user_id)
            if member:
                greeting += f" {member['member_name']} ({member['company_name']})"

        greeting += "\nHow can I help you with BNI today?"

        return JSONResponse({
            "status": "success",
            "conversation": f"User: {question}\nAI: {greeting}",
            "ai_summary": greeting,
            "ai_sql_generated": None,
            "is_general_knowledge": True
        })

    if data.is_general_knowledge or is_general_bni_question(question):
        summary = get_bni_knowledge_response(question)
        return JSONResponse({
            "status": "success",
            "conversation": f"User: {question}\nAI: {summary}",
            "ai_summary": summary,
            "ai_sql_generated": None,
            "is_general_knowledge": True
        })

    matched = find_closest_member_name(question)
    if matched:
        matched_name, matched_id = matched
        question = f"{question} (Matched ID: {matched_id}, Name: {matched_name})"

    sql = await generate_query_from_question(question, user_id)

    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MySQL error: {e}")

    print(f"[User ID]: {user_id}")
    print(f"[User Question]: {data.question}")
    print(f"[Generated SQL]: {sql}")
    print(f"[SQL Result Rows]: {json.dumps(rows, indent=2)}")
    
    
    ai_response = generate_friendly_summary(data.question, rows, user_id)

    if user_id:
       chain = get_conversation_chain(user_id)
       chain.run(f"User asked: {data.question}\nAI responded: {ai_response}")

        
    summary = normalize_text(clean_text(ai_response))
    conversation = normalize_text(f"User: {data.question}\nAI: {summary}")

    return JSONResponse({
        "status": "success",
        "conversation": conversation,
        "ai_summary": summary,
        "ai_sql_generated": sql,
        "is_general_knowledge": False
    }, headers={"Content-Type": "application/json; charset=utf-8"})

# Optional: Reset memory for a user
@app.post("/reset_memory/{user_id}")
async def reset_user_memory(user_id: int):
    if user_id in user_memory_store:
        del user_memory_store[user_id]
    return {"status": "memory_reset", "user_id": user_id}


