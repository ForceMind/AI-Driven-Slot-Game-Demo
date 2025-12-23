from llm_client import LLMClient
from models import LLMConfig
import json

def test_json_cleaning():
    print("Testing JSON Cleaning Logic...")
    
    # Test Case 1: Perfect JSON
    raw1 = '{"matrix": [], "total_payout": 0}'
    clean1 = LLMClient._clean_json_content(raw1)
    assert json.loads(clean1) == {"matrix": [], "total_payout": 0}
    print("PASS: Perfect JSON")

    # Test Case 2: Markdown Block
    raw2 = '```json\n{"matrix": [], "total_payout": 0}\n```'
    clean2 = LLMClient._clean_json_content(raw2)
    assert json.loads(clean2) == {"matrix": [], "total_payout": 0}
    print("PASS: Markdown Block")

    # Test Case 3: Conversational Text
    raw3 = 'Here is the result:\n```json\n{"matrix": [], "total_payout": 0}\n```\nHope you like it.'
    clean3 = LLMClient._clean_json_content(raw3)
    assert json.loads(clean3) == {"matrix": [], "total_payout": 0}
    print("PASS: Conversational Text")

    # Test Case 4: No Markdown but extra text
    raw4 = 'Sure! {"matrix": [], "total_payout": 0} is the result.'
    clean4 = LLMClient._clean_json_content(raw4)
    assert json.loads(clean4) == {"matrix": [], "total_payout": 0}
    print("PASS: No Markdown but extra text")
    
    # Test Case 5: The specific error reported by user (Likely partial string or escaping issue)
    # The error "LLM Generation Failed: '\n "matrix"'" suggests the cleaning might be returning a string starting with newline/quote?
    # Or maybe the content is literally just that string?
    raw5 = '\n  "matrix"' # Invalid JSON
    try:
        clean5 = LLMClient._clean_json_content(raw5)
        json.loads(clean5)
    except:
        print("PASS: Correctly failed on invalid JSON")

    print("All tests passed!")

if __name__ == "__main__":
    test_json_cleaning()
