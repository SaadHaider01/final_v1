
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to your GGUF model file
LLM_MODEL_PATH = os.path.join(BASE_DIR, "models", "mistral-7b-instruct-v0.2.Q4_K_M.gguf")

# LLM runtime parameters
LLM_RUNTIME = {
    "n_ctx": 2048,
    "temperature": 0.0,
    "max_tokens": 128,
    # 8 threads is ideal for your i5-11400H (12 logical cores)
    "n_threads": 8,
    # Offloading 20 layers to your GTX 1650 will drastically speed up validation
    "n_gpu_layers": 20,
}

# Multi-module detection: minimum chunk similarity to count a module
MODULE_SIMILARITY_THRESHOLD = 0.5
