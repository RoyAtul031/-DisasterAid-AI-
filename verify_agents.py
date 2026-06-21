import os
import asyncio
import sys
from dotenv import load_dotenv

# Load local .env if available
load_dotenv()

# Add workspace to python path so we can import backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents import orchestrate_disaster_aid

# The 6 test cases from Section 6.2
TEST_CASES = [
    {
        "id": "TEST 1 - Critical Severity",
        "input": "I am trapped on my roof in Durgapur. Water is rising fast. I cannot get down.",
        "location": "Durgapur, West Bengal",
        "expected_severity": "CRITICAL"
    },
    {
        "id": "TEST 2 - Medical Emergency",
        "input": "My mother is injured. We are near Asansol. Roads are flooded. Where is hospital?",
        "location": "Asansol, West Bengal",
        "expected_severity": "HIGH"
    },
    {
        "id": "TEST 3 - Multi-need Family",
        "input": "Family of 5 stranded in Howrah. Need shelter, food, and safe routes. Kids with us.",
        "location": "Howrah, West Bengal",
        "expected_severity": "HIGH"
    },
    {
        "id": "TEST 4 - Bengali Input",
        "input": "আমরা কলকাতায় আছি। বন্যার জল বাড়ছে। সাহায্য করুন।",
        "location": "Kolkata, West Bengal",
        "expected_severity": "HIGH"  # "বন্যার জল বাড়ছে" (Water rising) is High
    },
    {
        "id": "TEST 5 - Advisory Level",
        "input": "Cyclone warning in West Bengal next week. How should I prepare?",
        "location": "West Bengal, India",
        "expected_severity": "ADVISORY"
    },
    {
        "id": "TEST 6 - Food Specific",
        "input": "We have not eaten for 2 days. Where can we get food near Midnapore?",
        "location": "Midnapore, West Bengal",
        "expected_severity": "HIGH"  # "no food" is High
    }
]

async def run_verification():
    print("=" * 60)
    print("         DISASTERAID AI SYSTEM VERIFICATION")
    print("=" * 60)

    # Check API Key
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment!")
        print("Please copy .env.example to .env and configure your Gemini API Key to run tests.")
        return

    # Check Search keys
    search_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    if not search_key or not cse_id:
        print("⚠️ WARNING: Google Custom Search API keys not set. Search tool will run in Fallback Mode.")

    print("\n--- Starting Test Suite ---")
    
    passed_tests = 0
    for case in TEST_CASES:
        print(f"\n▶ Running: {case['id']}")
        print(f"  Input: \"{case['input']}\"")
        print(f"  Location Context: {case['location']}")
        
        try:
            # Execute agent orchestration
            result = await orchestrate_disaster_aid(case['input'], case['location'])
            
            print(f"  Assessed Severity: {result['severity']} (Expected: {case['expected_severity']})")
            print(f"  Detected Language: {result['language']}")
            print(f"  --- coordinator response output excerpt ---")
            
            # Print first 5 lines and last 5 lines of response
            lines = result['response'].split('\n')
            if len(lines) > 10:
                for line in lines[:5]:
                    print(f"  {line}")
                print("  ...")
                for line in lines[-5:]:
                    print(f"  {line}")
            else:
                for line in lines:
                    print(f"  {line}")
            print(f"  -------------------------------------------")
            
            # Basic validation assertions
            if "Bengali" in case['id']:
                severity_correct = result['severity'] in ["HIGH", "CRITICAL"]
            else:
                severity_correct = result['severity'] == case['expected_severity']
            
            # Test 1 must contain 112 escalation instructions
            has_emergency_warnings = True
            if case['expected_severity'] == "CRITICAL" and "112" not in result['response']:
                print("❌ FAIL: Critical situation did not include emergency warning / 112.")
                has_emergency_warnings = False
                
            # Test 4 language must be Bengali
            language_correct = True
            if "Bengali" in case['id'] and result['language'] != "bengali":
                print(f"❌ FAIL: Expected Bengali response, but got {result['language']}.")
                language_correct = False
                
            if severity_correct and has_emergency_warnings and language_correct:
                print(f"✅ {case['id']} Passed Verification!")
                passed_tests += 1
            else:
                print(f"❌ {case['id']} Failed Verification checks.")
                
        except Exception as err:
            print(f"❌ {case['id']} Errored: {str(err)}")

    print("\n" + "=" * 60)
    print(f"Verification Summary: {passed_tests} / {len(TEST_CASES)} passed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_verification())
