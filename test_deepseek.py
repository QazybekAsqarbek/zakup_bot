#!/usr/bin/env python
"""
Quick test to verify DeepSeek API is working
"""

import sys
from openai import OpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

def test_deepseek():
    print("="*60)
    print("Testing DeepSeek API Connection")
    print("="*60)
    
    # Check API key
    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set in .env")
        sys.exit(1)
    
    print(f"✅ API Key found: {DEEPSEEK_API_KEY[:10]}...")
    print(f"✅ Base URL: {DEEPSEEK_BASE_URL}")
    print(f"✅ Model: {DEEPSEEK_MODEL}")
    print()
    
    # Initialize client
    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
        print("✅ Client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        sys.exit(1)
    
    # Test simple API call
    print("\n🤖 Testing simple API call...")
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "user", "content": "Return only the word 'success' if you can read this."}
            ],
            max_tokens=10,
            temperature=0.0,
            timeout=30.0
        )
        
        result = response.choices[0].message.content
        print(f"✅ API Response: {result}")
        
        if "success" in result.lower():
            print("\n" + "="*60)
            print("🎉 DeepSeek API is working correctly!")
            print("="*60)
        else:
            print("\n⚠️ API responded but with unexpected content")
            
    except Exception as e:
        print(f"\n❌ API call failed: {e}")
        print("\nPossible issues:")
        print("1. Invalid API key")
        print("2. Network/firewall blocking request")
        print("3. API quota exceeded")
        print("4. DeepSeek service is down")
        sys.exit(1)

if __name__ == "__main__":
    test_deepseek()
