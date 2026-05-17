"""
services/grounding_validator.py
-------------------------------
Implements STRICT CURRICULUM GROUNDING.
Detects when a question introduces external application domains not explicitly
covered in the syllabus, preventing semantic stretching (e.g., matching "Kubernetes"
to a "security" syllabus).
"""

import re

# Configurable list of external domains that often cause semantic stretching
EXTERNAL_DOMAINS = [
    "blockchain",
    "cryptocurrency",
    "ethereum",
    "kubernetes",
    "docker",
    "cnn",
    "convolutional neural network",
    "deep learning",
    "recommendation engine",
    "recommender system",
    "hadoop",
    "cloud-native",
    "devops",
    "malware detection",
    "neural network",
    "microservices",
    "smart contract",
    "pod security",
    "wallets"
]

def _extract_text(chunks) -> str:
    """Safely extract text from chunks, skipping any reference/bibliography markers if they slipped through."""
    text_parts = []
    for c in chunks:
        # Step 4: Defense in depth against reference book leakage
        if isinstance(c, dict) and "text" in c:
            text = c["text"]
        elif isinstance(c, tuple):
            text = c[0]
        else:
            text = str(c)
            
        text_lower = text.lower()
        # Basic check to avoid grounding against references (if any slipped in)
        if "reference books" in text_lower or "bibliography" in text_lower:
            continue
            
        text_parts.append(text_lower)
    return " ".join(text_parts)


def detect_external_domain(question: str, chunks: list) -> str:
    """
    Returns the name of an external domain if one is found in the question
    but NOT found in the syllabus chunks. Returns None otherwise.
    """
    question_lower = question.lower()
    syllabus_text = _extract_text(chunks)
    
    for domain in EXTERNAL_DOMAINS:
        # Check if the question explicitly asks about this domain
        if re.search(r'\b' + re.escape(domain) + r'\b', question_lower):
            # If the domain is NOT in the syllabus text, it's an external intrusion
            if not re.search(r'\b' + re.escape(domain) + r'\b', syllabus_text):
                return domain
                
    return None

def is_explicitly_grounded(question: str, chunks: list, q_type: str = "unknown") -> tuple[bool, str]:
    """
    Returns (is_grounded, rejection_reason).
    """
    external_domain = detect_external_domain(question, chunks)
    
    if external_domain:
        return False, f"Question introduces external application domain '{external_domain}' not explicitly covered in syllabus."
        
    return True, ""
