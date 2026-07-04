
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

# --------------------------------------------------
# Curriculum Scope Validator
# --------------------------------------------------

# Master switch — set to False to disable the gate entirely (for debugging).
SCOPE_VALIDATOR_ENABLED = True

# Minimum retrieval similarity that activates the scope check.
# Matches THRESHOLD_WEAK from question_analyzer.py so that the scope
# validator runs for any question that passes the similarity gate.
SCOPE_HIGH_SIM_THR = 0.72

# Minimum concept overlap score required to pass the scope gate.
# Questions below this threshold are rejected as OUT_OF_CURRICULUM without
# invoking the LLM.  Lower = more permissive, higher = stricter.
SCOPE_OVERLAP_MIN_THR = 0.24

# Cosine similarity cutoff for word-level matches.
# Similarities below this are treated as 0.0 to filter out dense embedding noise.
SCOPE_SEMANTIC_CUTOFF = 0.86


# Number of domain-specific concepts to extract per syllabus at ingestion time.
SCOPE_CONCEPTS_TOP_N = 150


