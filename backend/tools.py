import os
import httpx
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any

async def google_search(query: str, location: str = "") -> str:
    """
    Real-time Google Custom Search for disaster relief resources.
    Uses Google Custom Search JSON API.
    Falls back to a simpler query if no results found.
    """
    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        return "TOOL ERROR: Search API keys not configured. Please supply info from emergency contacts or memory."

    # Add location context if not in query
    full_query = f"{query} {location}" if location and location not in query else query
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": full_query,
        "num": 5, # Get 5 results, agent picks best
        "gl": "in", # Geo-target India
        "hl": "en",
        "safe": "active",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            if not items:
                # Try simpler fallback query
                params["q"] = f"emergency relief {location}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    items = response.json().get("items", [])
                if not items:
                    return f"No search results for: {full_query}. Try ndma.gov.in directly."
            
            results = []
            for item in items[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                results.append(f"SOURCE: {title}\nINFO: {snippet}\nURL: {link}")
            return "\n\n".join(results)
    except httpx.TimeoutException:
        return "Search timed out. Provide info from memory or tell user to call 1078."
    except Exception as e:
        return f"Search error: {str(e)}. Fallback: ndma.gov.in | 1078 | 112"

async def fetch_disaster_alerts(location: str = "India") -> str:
    """
    Fetches real-time disaster alerts from GDACS (UN system).
    Completely free - no API key required.
    Auto-filters alerts relevant to user location.
    """
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get("https://www.gdacs.org/xml/rss.xml")
            response.raise_for_status()
            root = ET.fromstring(response.content)
            all_alerts = []
            for item in root.findall(".//item")[:20]:
                title = item.find("title")
                desc = item.find("description")
                pubdate = item.find("pubDate")
                link = item.find("link")
                if title is not None and title.text:
                    all_alerts.append({
                        "title": title.text,
                        "desc": (desc.text or "")[:300] if desc is not None else "",
                        "date": pubdate.text if pubdate is not None else "Unknown",
                        "link": link.text if link is not None else "",
                    })
            
            # Filter for user location (India by default)
            loc_lower = location.lower()
            loc_keywords = [
                loc_lower, "india", "bengal", "bay of bengal",
                "cyclone", "flood", "earthquake", "landslide"
            ]
            relevant = [
                a for a in all_alerts
                if any(kw in a["title"].lower() or kw in a["desc"].lower() for kw in loc_keywords)
            ]
            
            # Fall back to all alerts if nothing region-specific
            display = relevant[:5] if relevant else all_alerts[:3]
            if not display:
                return "No active GDACS alerts found. Check ndma.gov.in for local alerts."
                
            fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            lines = [f"GDACS LIVE ALERTS (fetched {fetched_at}):"]
            for a in display:
                lines.append(f"\n ALERT: {a['title']}")
                lines.append(f" DATE: {a['date']}")
                if a["desc"]:
                    lines.append(f" INFO: {a['desc'][:200]}")
            lines.append("\nSource: UN GDACS - gdacs.org")
            return "\n".join(lines)
    except httpx.TimeoutException:
        return "GDACS API timeout. Manual check: gdacs.org | ndma.gov.in"
    except ET.ParseError:
        return "GDACS data parsing error. Check gdacs.org directly."
    except Exception as e:
        return f"GDACS error: {str(e)}. Check ndma.gov.in for alerts."

def assess_situation_severity(situation_description: str) -> Dict[str, Any]:
    """
    Analyzes user's situation description and returns severity level.
    Determines whether to escalate to 112 immediately.
    Severity levels:
    CRITICAL → Life in immediate danger → call 112 NOW
    HIGH → Urgent need, hours matter → fast resource finding
    MODERATE → Serious situation, not immediately life-threatening
    ADVISORY → Precautionary, user wants to prepare
    """
    desc = situation_description.lower()
    
    # Life-threatening indicators (English, Hindi, Bengali)
    critical = [
        "trapped", "drowning", "cannot breathe", "unconscious",
        "bleeding heavily", "heart attack", "dying", "help me",
        "stuck in water", "roof collapsed", "buried", "swept away",
        "আটকে", "ডুব", "নিঃশ্বাস", "রক্ত", "মারা", "বাঁচান", "ভেঙে", "সাহায্য করুন",
        "फंसा", "फंसे", "डूब", "सांस", "बेहोश", "खून", "मर", "मदद करो", "बचाओ", "मलबे"
    ]
    
    # Urgent but not immediately life-threatening (English, Hindi, Bengali)
    high = [
        "flood", "rising water", "water rising", "stranded", "no food",
        "no water", "shelter", "evacuation", "cyclone", "landslide",
        "earthquake", "family missing", "children with me",
        "not eaten", "hungry", "starving", "need food",
        "বন্যা", "জল বাড়ছে", "খাবার নেই", "খাবার পাচ্ছি না", "জল নেই", "আশ্রয়", "সাইক্লোন", "ঝড়", "ভূমিধস", "খোঁজ",
        "बाढ़", "पानी बढ़", "खाना नहीं", "भूखा", "भूखे", "पानी नहीं", "शरण", "चक्रवात", "तूफान", "भूस्खलन", "लापता"
    ]
    
    # Serious but more time available
    moderate = [
        "road blocked", "power out", "phone dying", "low supplies",
        "worried", "scared", "neighbors", "community",
        "রাস্তা বন্ধ", "বিদ্যুৎ", "ফোন", "উদ্বিগ্ন", "ভীত",
        "रास्ता बंद", "बिजली", "फोन", "चिंता", "डर"
    ]

    critical_hits = sum(1 for kw in critical if kw in desc)
    high_hits = sum(1 for kw in high if kw in desc)
    moderate_hits = sum(1 for kw in moderate if kw in desc)

    # Precautionary indicators that imply prep/information queries rather than active crisis
    advisory_downgrade = any(kw in desc for kw in [
        "prepare", "preparation", "how should i", "next week", "forecast", "news", "advice",
        "প্রস্তুতি", "তৈরি", "সতর্কবার্তা",
        "तैयारी", "चेतावनी", "पूर्वानुमान"
    ])

    if critical_hits >= 1 and not advisory_downgrade:
        return {
            "severity": "CRITICAL",
            "call_112_now": True,
            "message": "🚨 CRITICAL: Call 112 NOW. Do not wait.",
            "priority_order": ["Call 112", "Medical", "Rescue", "Shelter"],
            "response_tone": "URGENT - lead with 112 instruction",
        }
    elif (high_hits >= 1 or (critical_hits >= 1 and advisory_downgrade)) and not advisory_downgrade:
        return {
            "severity": "HIGH",
            "call_112_now": False,
            "message": "⚠️ HIGH PRIORITY situation detected.",
            "priority_order": ["Shelter", "Food/Water", "Medical", "Safety info"],
            "response_tone": "URGENT but calm - focus on resources",
        }
    elif (moderate_hits >= 1 or high_hits >= 1) and not advisory_downgrade:
        return {
            "severity": "MODERATE",
            "call_112_now": False,
            "message": "⚡ Moderate severity situation.",
            "priority_order": ["Safety info", "Prepare", "Monitor"],
            "response_tone": "Informative and preparatory",
        }
    else:
        return {
            "severity": "ADVISORY",
            "call_112_now": False,
            "message": "ℹ️ Advisory level - precautionary.",
            "priority_order": ["Stay informed", "Prepare kit", "Monitor news"],
            "response_tone": "Calm and educational",
        }

def get_emergency_contacts(location: str) -> Dict[str, Any]:
    """
    Returns verified emergency contact numbers for India.
    Static data - these numbers are verified and stable.
    """
    # Always-valid national numbers
    national = {
        "National Emergency": "112",
        "Ambulance": "108",
        "NDMA Helpline": "1078",
        "Fire Service": "101",
        "Police": "100",
        "Women Helpline": "1091",
        "Child Helpline": "1098",
        "NDRF Headquarters": "011-24363260",
    }
    
    # State-specific (expand as needed)
    loc = location.lower()
    state = {}
    if any(p in loc for p in ["west bengal", "bengal", "kolkata", "durgapur", "howrah", "asansol", "siliguri", "bardhaman"]):
        state = {
            "WB Disaster Mgmt Dept": "033-22143526",
            "WB Flood Control Room": "033-22536663",
            "Kolkata Police Control": "033-22141312",
            "WBSDMA": "1070",
        }
    elif any(p in loc for p in ["mumbai", "maharashtra", "pune"]):
        state = {
            "Maharashtra SDMA": "022-22025027",
            "Mumbai Disaster Cell": "022-22694727",
        }
    elif any(p in loc for p in ["odisha", "bhubaneswar", "cuttack", "puri"]):
        state = {
            "Odisha SDMA": "0674-2534177",
            "Odisha Flood Control": "0674-2395398",
        }
    elif any(p in loc for p in ["assam", "guwahati", "dibrugarh"]):
        state = {
            "Assam SDMA": "0361-2237230",
            "Assam Disaster Helpline": "1070",
        }
        
    return {
        "location": location,
        "national_contacts": national,
        "state_contacts": state,
        "web_resources": [
            "ndma.gov.in",
            "ndrf.gov.in",
            "gdacs.org",
            "imd.gov.in (weather)"
        ]
    }
