#!/usr/bin/env python3
"""
Simple test script to verify Ollama connection and model availability.
"""
import json
import sys
from openai import OpenAI

def test_ollama_connection():
    """Test basic connection to Ollama API."""
    print("=" * 60)
    print("Testing Ollama Connection")
    print("=" * 60)

    try:
        # Initialize OpenAI client pointing to Ollama
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"  # Ollama doesn't need a real API key
        )

        # Test 1: List available models
        print("\n1. Checking available models...")
        try:
            models = client.models.list()
            if models and models.data:
                print(f"   ✓ Found {len(models.data)} model(s)")
                for model in models.data:
                    print(f"   - {model.id}")
            else:
                print("   ⚠ Could not list models via API, but continuing test...")
        except Exception as e:
            print(f"   ⚠ Could not list models: {e}, but continuing test...")

        # Test 2: Try a simple completion
        print("\n2. Testing model completion with 'qwen2.5-coder:7b'...")
        response = client.chat.completions.create(
            model="qwen2.5-coder:7b",
            messages=[
                {"role": "user", "content": "Say 'Hello, Ollama is working!' and nothing else."}
            ],
            temperature=0.1,
            max_tokens=50
        )

        reply = response.choices[0].message.content
        print(f"   ✓ Model response: {reply}")

        # Test 3: Check model metadata
        print("\n3. Checking model metadata...")
        print(f"   - Model: {response.model}")
        print(f"   - Finish reason: {response.choices[0].finish_reason}")

        print("\n" + "=" * 60)
        print("✓ All tests passed! Ollama is working correctly.")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Ollama is running:")
        print("   OLLAMA_MODELS=/Volumes/Zuk/ollama/models ollama serve &")
        print("2. Verify the model is available:")
        print("   curl http://localhost:11434/api/tags")
        print("3. Check that the model name matches exactly")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_ollama_connection()
    sys.exit(0 if success else 1)
