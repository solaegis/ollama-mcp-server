import time
import os
import json
import urllib.request
import urllib.error
from prometheus_client import start_http_server, Gauge

# Metrics definitions
MODEL_COUNT = Gauge('ollama_model_count', 'Total number of models pulled')
MODEL_VRAM_USAGE = Gauge('ollama_model_vram_usage_bytes', 'VRAM usage per model', ['model'])
MODEL_LOADED = Gauge('ollama_model_loaded', 'Is model currently loaded in memory', ['model'])
OLLAMA_UP = Gauge('ollama_up', 'Ollama server status (1 for up, 0 for down)')

# Environment configuration
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
METRICS_PORT = int(os.environ.get("METRICS_PORT", 9110))

def collect_metrics():
    try:
        # Check if Ollama is up and get tags
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as resp:
            if resp.status == 200:
                OLLAMA_UP.set(1)
                data = json.loads(resp.read().decode())
                models = data.get('models', [])
                MODEL_COUNT.set(len(models))
            else:
                OLLAMA_UP.set(0)

        # Get loaded models (ps)
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                loaded_models = data.get('models', [])
                
                # Reset loaded state values
                # Note: In a production exporter we would handle metrics cleanup better
                for m in loaded_models:
                    name = m['name']
                    vram = m.get('size_vram', 0)
                    MODEL_VRAM_USAGE.labels(model=name).set(vram)
                    MODEL_LOADED.labels(model=name).set(1)
    except urllib.error.URLError:
        OLLAMA_UP.set(0)
    except Exception as e:
        print(f"Error collecting metrics: {e}")
        OLLAMA_UP.set(0)

if __name__ == "__main__":
    # Start Prometheus server
    start_http_server(METRICS_PORT)
    print(f"Ollama Metrics Exporter running on http://0.0.0.0:{METRICS_PORT}/metrics")
    print(f"Scraping Ollama at: {OLLAMA_URL}")
    
    while True:
        collect_metrics()
        time.sleep(15)
