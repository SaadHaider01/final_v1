# models/model_test.py
import os, sys, time
from llama_cpp import Llama

# ====== UPDATE THIS if your filename changes ======
MODEL_FILENAME = "Phi-3-mini-4k-instruct-q4.gguf"
# =================================================

model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), MODEL_FILENAME))
print("Trying model path:", model_path)
if not os.path.exists(model_path):
    print("ERROR: model file not found at:", model_path)
    sys.exit(1)

print("Loading model (this can take ~10-60s depending on disk/CPU)...")
# create instance (keep minimal args)
llm = Llama(model_path=model_path, n_ctx=2048)

# show available attributes for debugging
attrs = sorted([a for a in dir(llm) if not a.startswith("_")])
print("\nAvailable llama-cpp-python attributes (short list):")
print(", ".join([a for a in attrs if len(a) < 20][:60]))
print("\n(If you want the full list paste it here and I can interpret.)\n")

# The user prompt we'll test with
PROMPT = "Is the CIA Triad a cybersecurity concept? Answer EXACTLY in this format: YES - <one short sentence>"

# try multiple invocation styles, in order of common versions
def try_chat():
    # some builds accept llm.chat(messages=[...])
    if hasattr(llm, "chat"):
        try:
            print("[info] Using llm.chat(...)")
            resp = llm.chat(
                messages=[
                    {"role": "system", "content": "You are a short YES/NO classifier."},
                    {"role": "user", "content": PROMPT},
                ],
                max_tokens=120,
                temperature=0.0,
            )
            # response content path may vary
            # common formats:
            if "choices" in resp and resp["choices"]:
                c = resp["choices"][0]
                # chat variants sometimes have ["message"]["content"]
                text = c.get("message", {}).get("content") or c.get("text") or str(c)
            else:
                text = resp.get("text") or str(resp)
            return text
        except Exception as e:
            print("[warn] llm.chat raised:", repr(e))
    return None

def try_generate():
    if hasattr(llm, "generate"):
        try:
            print("[info] Using llm.generate(...)")
            resp = llm.generate(
                prompt=PROMPT,
                max_tokens=120,
                temperature=0.0,
            )
            # generate variants often return .generations or choices
            if isinstance(resp, dict):
                if "results" in resp and resp["results"]:
                    # try to pick text
                    r = resp["results"][0]
                    text = r.get("text") or str(r)
                elif "choices" in resp and resp["choices"]:
                    text = resp["choices"][0].get("text") or str(resp["choices"][0])
                else:
                    text = resp.get("text") or str(resp)
            else:
                text = str(resp)
            return text
        except Exception as e:
            print("[warn] llm.generate raised:", repr(e))
    return None

def try_create():
    if hasattr(llm, "create"):
        try:
            print("[info] Using llm.create(...)")
            resp = llm.create(
                prompt=PROMPT,
                max_tokens=120,
                temperature=0.0,
            )
            # older versions returned resp.get("text")
            text = None
            if isinstance(resp, dict):
                text = resp.get("text") or (resp.get("choices") and resp["choices"][0].get("text"))
            if text is None:
                text = str(resp)
            return text
        except Exception as e:
            print("[warn] llm.create raised:", repr(e))
    return None

def try_call():
    # some versions implement __call__ so you can do llm(prompt=...)
    try:
        print("[info] Trying llm(...) / llm(prompt=...)")
        # try keyword form first
        try:
            resp = llm(prompt=PROMPT, max_tokens=120, temperature=0.0)
        except TypeError:
            # try positional
            resp = llm(PROMPT, max_tokens=120, temperature=0.0)
        # try to extract text
        if isinstance(resp, dict):
            text = resp.get("text") or (resp.get("choices") and resp["choices"][0].get("text"))
        else:
            text = str(resp)
        return text
    except Exception as e:
        print("[warn] llm(...) raised:", repr(e))
    return None

# order of attempts
attempts = [try_chat, try_generate, try_create, try_call]
result = None
for fn in attempts:
    result = fn()
    if result:
        print("\n[success] Obtained model output using", fn.__name__)
        print("---- MODEL OUTPUT START ----")
        print(result.strip())
        print("---- MODEL OUTPUT END ----")
        break

if result is None:
    print("\nERROR: Could not call the model via known methods. Here are debug hints:")
    print("- llama-cpp-python version:", getattr(llm, "__version__", "unknown"))
    print("- Available attributes preview above; if 'chat', 'create', 'generate', '__call__' are missing, paste the attribute list here.")
    print("- As a fallback, try installing a different version: pip install 'llama-cpp-python==0.3.15' or similar.")
    sys.exit(2)
