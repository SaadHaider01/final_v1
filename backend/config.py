
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to your GGUF model file
LLM_MODEL_PATH = os.path.join(BASE_DIR, "models", "mistral-7b-instruct-v0.2.Q4_K_M.gguf")

# LLM runtime parameters
LLM_RUNTIME = {
    "n_ctx": 2048,
    "temperature": 0.0,
    "max_tokens": 128,
    # threads: tune to your CPU cores; e.g., 4
    "n_threads": 4,
}
