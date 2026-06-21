import os
import asyncio
import logging
import re
import httpx
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from backend.tools import (
    google_search,
    fetch_disaster_alerts,
    get_emergency_contacts,
    assess_situation_severity
)

# Configure logger
logger = logging.getLogger("disasteraid.agents")
logging.basicConfig(level=logging.INFO)

async def call_groq(system_instruction: str, prompt: str, temperature: float = 0.2) -> Optional[str]:
    """
    Calls the Groq chat completions API with retries on rate limits.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        logger.error("Groq API key not set.")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Models to try in order
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    retries = 3
    delay = 2.0
    
    for model in models:
        for attempt in range(retries):
            try:
                logger.info(f"Attempting response generation with Groq model {model} (Attempt {attempt+1})...")
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": 2048
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        text = response.json()["choices"][0]["message"]["content"]
                        logger.info(f"Groq generation successful with model {model}!")
                        return text
                    elif response.status_code == 429: # Rate limit
                        logger.warning(f"Groq API rate limit with model {model}. Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        logger.warning(f"Groq API error with model {model} (status {response.status_code}): {response.text}")
                        break # Try next model if it's not a rate limit
            except Exception as e:
                logger.warning(f"Groq exception with model {model}: {str(e)}")
                break # Try next model on network/timeout exception
            
    return None

def detect_script_language(text: str) -> str:
    """Detects whether text uses Bengali, Devanagari (Hindi), or English script."""
    bengali_chars = len(re.findall(r'[\u0980-\u09ff]', text))
    hindi_chars = len(re.findall(r'[\u0900-\u097f]', text))
    
    if bengali_chars > 0 and bengali_chars >= hindi_chars:
        return "bengali"
    elif hindi_chars > 0:
        return "hindi"
    return "english"

async def orchestrate_disaster_aid(user_message: str, current_location: str) -> Dict[str, Any]:
    """
    Optimized orchestration function:
    1. Assess situation severity (Python local logic)
    2. Detect language (Python script detection)
    3. Determine categories of needs
    4. Fetch ALL resources (Custom Searches, GDACS Alerts, Emergency Numbers) in parallel (Python)
    5. Compile and format final response in a SINGLE LLM call (Groq)
    """
    logger.info(f"Orchestrating DisasterAid request for location: {current_location}")
    
    # Step 1: Assess severity
    severity_info = assess_situation_severity(user_message)
    severity = severity_info["severity"]
    
    # Step 2: Detect Language
    lang = detect_script_language(user_message)
    logger.info(f"Detected script language: {lang}, Severity: {severity}")
    
    # Step 3: Determine categories needed based on keywords
    msg_lower = user_message.lower()
    
    need_shelter = any(k in msg_lower for k in ["shelter", "safe place", "stranded", "flooding", "stay", "accommodation", "roof", "cyclone", "bengali", "hindi", "help"])
    need_medical = any(k in msg_lower for k in ["hospital", "injured", "sick", "medical", "hurt", "bleeding", "doctor", "ambulance", "medicine", "wound", "injured"])
    need_food = any(k in msg_lower for k in ["food", "hungry", "water", "thirsty", "starving", "eat", "drink", "tanker", "meals"])
    need_safety = any(k in msg_lower for k in ["alert", "road", "evacuation", "warning", "safe", "weather", "cyclone", "flood", "closed"])
    
    # If it's a generic plea or multiple needs, fetch all
    if not (need_shelter or need_medical or need_food or need_safety) or len(msg_lower) < 15:
        need_shelter = need_medical = need_food = need_safety = True

    # Step 4: Fetch Resources in Parallel
    search_tasks = {}
    
    if need_shelter:
        search_tasks["shelter_1"] = google_search("emergency shelter relief camp", current_location)
        search_tasks["shelter_2"] = google_search("evacuation center flood cyclone disaster", current_location)
        search_tasks["shelter_3"] = google_search("government relief camp NDRF", current_location)
        
    if need_medical:
        search_tasks["medical_1"] = google_search("hospital operational flood disaster", current_location)
        search_tasks["medical_2"] = google_search("NDRF medical camp Red Cross relief", current_location)
        search_tasks["medical_3"] = google_search("mobile medical unit ambulance", current_location)
        
    if need_food:
        search_tasks["food_1"] = google_search("food relief distribution community kitchen langar", current_location)
        search_tasks["food_2"] = google_search("drinking water supply tanker", current_location)
        search_tasks["food_3"] = google_search("NGO food camp ISKCON Goonj", current_location)
        
    if need_safety:
        search_tasks["safety_1"] = google_search("road closed flooded today", current_location)
        search_tasks["safety_2"] = google_search("evacuation order warning IMD weather red alert", current_location)
        
    # Always fetch live UN alerts and emergency numbers
    search_tasks["gdacs"] = fetch_disaster_alerts(current_location)
    
    # Run all search queries concurrently in Python (takes ~1-2 seconds total)
    logger.info(f"Pre-fetching {len(search_tasks)} database/web search resources in parallel...")
    task_keys = list(search_tasks.keys())
    fetched_results = await asyncio.gather(*[search_tasks[k] for k in task_keys], return_exceptions=True)
    
    # Organize search results
    resources = {k: ("Error fetching data" if isinstance(r, Exception) else r) for k, r in zip(task_keys, fetched_results)}
    
    # Retrieve local emergency contacts directory
    local_contacts = get_emergency_contacts(current_location)
    
    # Compile reports for context
    shelter_context = "\n".join([resources[k] for k in ["shelter_1", "shelter_2", "shelter_3"] if k in resources])
    medical_context = "\n".join([resources[k] for k in ["medical_1", "medical_2", "medical_3"] if k in resources])
    food_context = "\n".join([resources[k] for k in ["food_1", "food_2", "food_3"] if k in resources])
    safety_context = "\n".join([resources[k] for k in ["safety_1", "safety_2"] if k in resources])
    gdacs_context = resources.get("gdacs", "No live UN alerts.")
    
    # Step 5: Unified Prompt Construction
    root_instruction = (
        "You are DisasterAid AI, a compassionate emergency response coordinator.\n"
        "Your mission: Help people affected by disasters find immediate relief as fast as possible.\n\n"
        "━━━ STEP 1: ASSESS SEVERITY (ALWAYS FIRST) ━━━\n"
        f"The assessed severity is: {severity}.\n"
        "If CRITICAL → Immediately tell user: \"🚨 CALL 112 RIGHT NOW. Do not wait.\"\n"
        "Then STILL continue to find resources - do not stop at the alert.\n"
        "If HIGH → Begin with \"⚠️ This is urgent. Here is immediate help:\"\n"
        "If MODERATE → Begin with \"⚡ Here is what you need to know:\"\n"
        "If ADVISORY → Begin with \"ℹ️ Here is helpful information:\"\n\n"
        "━━━ STEP 2: COMPILE SUB-AGENT DATA ━━━\n"
        "Use ONLY the real-time search data provided below. Do not invent any shelters, hospitals, or food camps.\n\n"
        "━━━ STEP 3: RESPOND ENTIRELY IN THE SPECIFIED LANGUAGE ━━━\n"
        f"You MUST respond ENTIRELY in: {lang.upper()}.\n"
        "If user language is BENGALI → respond ENTIRELY in Bengali (Bengali script).\n"
        "If user language is HINDI → respond ENTIRELY in Hindi (Devanagari script).\n"
        "Otherwise → respond in English.\n"
        "Never mix languages. Keep the same language throughout the output.\n\n"
        "━━━ STEP 4: FORMAT RESPONSE ━━━\n"
        "Compile results into EXACTLY this structure:\n"
        "🆘 IMMEDIATE ACTION: [only if severity is CRITICAL]\n"
        "─────────────────────────────────────────\n"
        "🏠 SHELTER:\n"
        "[Shelter locations, addresses, contact numbers from search data]\n"
        "🏥 MEDICAL AID:\n"
        "[Hospitals, medical camps, ambulance info from search data]\n"
        "🍱 FOOD & WATER:\n"
        "[Distribution points, community kitchens, safety notes from search data]\n"
        "⚠️ SAFETY ALERTS:\n"
        "🚫 AVOID: [danger zones, flooded roads]\n"
        "✅ SAFE: [evacuation routes, safe areas]\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📞 EMERGENCY NUMBERS - CALL ANYTIME, 24/7:\n"
        "🆘 National Emergency: 112\n"
        "🚑 Ambulance: 108\n"
        "🏛️ NDMA Helpline: 1078\n"
        "🚒 Fire Service: 101\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Stay safe. Help is coming. 🙏\n\n"
        "━━━ TONE RULES ━━━\n"
        "✅ Calm, clear, compassionate - panic is contagious, so never panic\n"
        "✅ Specific - give names, addresses, phone numbers, not vague directions\n"
        "✅ Concise - people in crisis cannot read long paragraphs\n"
        "✅ Honest - if no specific resource found, say so and give the closest alternative (like NDMA helpline 1078)\n"
        "❌ Never say \"I don't know\" without offering an alternative\n"
        "❌ Never omit the emergency numbers at the end\n"
        "❌ Never respond in a different language than requested."
    )

    compiler_prompt = (
        f"User message: {user_message}\n"
        f"Current Location Context: {current_location}\n\n"
        f"--- REAL-TIME SHELTER SEARCH DATA ---\n{shelter_context if need_shelter else 'No shelter search requested.'}\n\n"
        f"--- REAL-TIME MEDICAL SEARCH DATA ---\n{medical_context if need_medical else 'No medical search requested.'}\n\n"
        f"--- REAL-TIME FOOD/WATER SEARCH DATA ---\n{food_context if need_food else 'No food search requested.'}\n\n"
        f"--- REAL-TIME ROAD/SAFETY SEARCH DATA ---\n{safety_context if need_safety else 'No safety search requested.'}\n\n"
        f"--- LIVE UN GDACS DISASTER ALERTS ---\n{gdacs_context}\n\n"
        f"--- LOCAL EMERGENCY DIRECTORY contacts ---\n{str(local_contacts)}\n"
    )

    # Step 6: Invoke LLM (Groq only)
    response_text = await call_groq(root_instruction, compiler_prompt)
    
    if not response_text:
        logger.error("Groq failed to generate a response.")
        raise Exception("Failed to generate response using Groq. Please check your API key and quotas.")
        
    return {
        "severity": severity,
        "language": lang,
        "response": response_text,
        "details": {
            "shelter": shelter_context,
            "medical": medical_context,
            "food": food_context,
            "safety": safety_context
        }
    }
