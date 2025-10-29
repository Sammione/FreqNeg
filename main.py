from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import re
from config import BASE_URL, FAQ_ENDPOINT, get_auth_headers

app = FastAPI(title="LUAN – Infracredit AI Bot")

# Allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fetch_faqs(token: str):
    """Fetch FAQs from the authenticated API endpoint"""
    url = f"{BASE_URL}{FAQ_ENDPOINT}"
    headers = get_auth_headers(token)
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            return response.json()
        except Exception as e:
            print("Could not parse JSON:", e)
            return None
    else:
        print(f"Error fetching FAQs: {response.status_code}, {response.text}")
        return None


# ----------------------------
#  Core helper functions
# ----------------------------
def search_faqs(query, faq_data):
    """Search across question, clauseName, and documentTypeName"""
    results = []
    if not faq_data or "data" not in faq_data:
        return results

    query = query.lower().strip().replace("?", "")
    faq_items = faq_data["data"].get("result", [])

    for item in faq_items:
        question = item.get("question", "").lower()
        clause = item.get("clauseName", "").lower()
        doc_type = item.get("documentTypeName", "").lower()
        response = item.get("response", "")
        submitted_by = item.get("submittedByUserName", "Unknown User")

        if query in question or query in clause or query in doc_type:
            results.append({
                "question": question,
                "answer": response,
                "clause": clause,
                "documentType": doc_type,
                "submittedBy": submitted_by
            })
    return results


def contains_fuzzy_command(text):
    fuzzy_keywords = [
        "show me", "list", "what is", "tell me about", "find", "display", "search for",
        "?", "on", "the", "fni", "frequently negotiated issue"
    ]
    text = text.lower()
    return any(keyword in text for keyword in fuzzy_keywords)


def clean_query(user_input):
    cleaned = re.sub(
        r"(show me|list|list out|what is|tell me about|find|tell me|display|search for|frequently negotiated issue|fni|on|\?)",
        "", user_input, flags=re.IGNORECASE
    )
    return cleaned.strip()


def show_greeting_and_examples(faq_data):
    faq_items = faq_data["data"].get("result", []) if faq_data and "data" in faq_data else []

    clause_names = list({item.get("clauseName", "") for item in faq_items if item.get("clauseName")})
    doc_names = list({item.get("documentTypeName", "") for item in faq_items if item.get("documentTypeName")})
    client_types = list({item.get("submittedByUserName", "") for item in faq_items if item.get("submittedByUserName")})

    clause_example = clause_names[0] if clause_names else "Clause 1"
    doc_example = doc_names[0] if doc_names else "Document 1"
    client_example = client_types[0] if client_types else "Client 1"

    return {
        "message": "Hi, i'm LUAN, Infracredit’s AI bot. How can I help you today?",
        "examples": [
            f"List Negotiated issue about document type '{doc_example}'",
            f"List Negotiated issue about client type '{client_example}'",
            f"Tell me about FNI for clause '{clause_example}'",
            f"Tell me about FNI for document '{doc_example}'",
            f"Show me about FNI for document '{doc_example}'",
            f"Show me about FNI for clause '{clause_example}'",
            f"What is the frequently negotiated issue for '{doc_example}'?"
        ]
    }




@app.get("/")
def root():
    return {"message": "LUAN API is running successfully"}


@app.get("/api/v1/greet")
def greet_user(authorization: str = Header(None)):
    """Send initial greeting + dynamic examples"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.replace("Bearer ", "")
    faq_data = fetch_faqs(token)
    if not faq_data:
        raise HTTPException(status_code=500, detail="Could not load FAQ data")

    return show_greeting_and_examples(faq_data)


@app.get("/api/v1/search")
def search_faq(query: str = Query(..., description="User query"),
               authorization: str = Header(None)):
    """Main search endpoint with fuzzy command handling"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.replace("Bearer ", "")
    faq_data = fetch_faqs(token)
    if not faq_data:
        raise HTTPException(status_code=500, detail="Could not load FAQ data")

    if contains_fuzzy_command(query):
        cleaned_query = clean_query(query)
        matches = search_faqs(cleaned_query, faq_data)
    else:
        matches = search_faqs(query, faq_data)

    if matches:
        return {"results": matches}
    else:
        return {"message": "No matches found. Try rephrasing your query or check the document title."}
