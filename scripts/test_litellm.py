import json
import os
import sys
import time
import urllib.request
import urllib.error

def test_litellm():
    api_key = os.environ.get("LITELLM_MASTER_KEY", "sk-local-dev-key")
    url = "http://localhost:4000/v1/chat/completions"
    data = {
        "model": "qwen2.5-coder-7b",
        "messages": [{"role": "user", "content": "Reply with just: ok"}],
        "max_tokens": 10
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    max_retries = 5
    retry_delay = 5

    print(f"Testing LiteLLM endpoint: {url}")
    print(f"Using model: {data['model']}")

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(data).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data['choices'][0]['message']['content']
                print(f"\nSuccess! Response: {content}")
                return True

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            print(f"\nAttempt {attempt}/{max_retries} failed with HTTP {e.code}")
            try:
                error_json = json.loads(body)
                print(f"Error details: {json.dumps(error_json, indent=2)}")
            except:
                print(f"Raw error body: {body}")
            
            if e.code == 401:
                print("Hint: Check your LITELLM_MASTER_KEY")
            
        except urllib.error.URLError as e:
            print(f"\nAttempt {attempt}/{max_retries} failed: {e.reason}")
            print("Hint: Is LiteLLM running? Check with 'task status'")
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"\nAttempt {attempt}/{max_retries} failed to parse response: {e}")
            
        except Exception as e:
            print(f"\nAttempt {attempt}/{max_retries} failed with unexpected error: {type(e).__name__}: {e}")

        if attempt < max_retries:
            print(f"Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    print("\nERROR: All test attempts failed.")
    return False

if __name__ == "__main__":
    if not test_litellm():
        sys.exit(1)
