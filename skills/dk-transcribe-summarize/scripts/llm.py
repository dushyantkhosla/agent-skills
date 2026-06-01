"""LLM interactions: OpenRouter transcription + LM Studio local summarization."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

from config import MODEL_NAME, LOCAL_MODEL_NAME, LMSTUDIO_URL
from audio import compress_audio_for_api, audio_to_data_uri


# ── OpenRouter (transcription) ─────────────────────────────────────────


def openrouter_chat(messages: list, max_tokens: int = 4000, temperature: float = 0) -> str:
    """Call the OpenRouter API for transcription."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=300,
    )
    if not resp.ok:
        print(f"OpenRouter error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    content = msg.get("content") or msg.get("reasoning") or ""
    for prefix in ("Transcription:", "Transcript:", "Here is the transcription:"):
        if content.startswith(prefix):
            content = content[len(prefix):]
            break
    if not content:
        print(f"DEBUG: empty content, full response: {json.dumps(data, indent=2)[:2000]}", file=sys.stderr)
    return content.strip()


def transcribe(audio_path: Path) -> str:
    """Transcribe audio via OpenRouter multimodal API."""
    raw_size = audio_path.stat().st_size
    estimated_b64 = raw_size * 4 // 3
    if estimated_b64 > 6_000_000:
        print("Audio is large; compressing for API upload...")
        audio_path = compress_audio_for_api(audio_path)

    data_uri = audio_to_data_uri(audio_path)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "audio_url", "audio_url": {"url": data_uri}},
                {
                    "type": "text",
                    "text": "Transcribe this audio. Output only the transcription, no commentary.",
                },
            ],
        }
    ]
    return openrouter_chat(messages, max_tokens=10000)


# ── LM Studio (local summarization) ────────────────────────────────────


def _lms(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["lms", *args], capture_output=True, text=True, timeout=timeout)


def ensure_lmstudio_ready(model_name: str) -> str:
    """Start LM Studio server if needed and load the model. Returns model name."""
    status = _lms(["server", "status"])
    if "running" not in status.stderr.lower() and "running" not in status.stdout.lower():
        print("Starting LM Studio server...")
        _lms(["server", "start"])
        import time
        for _ in range(12):
            time.sleep(5)
            s = _lms(["server", "status"])
            if "running" in s.stderr.lower() or "running" in s.stdout.lower():
                print("LM Studio server is running.")
                break
        else:
            print("Warning: LM Studio server may not have started in time.")
    else:
        print("LM Studio server is already running.")

    available = _lms(["ls"]).stdout
    if model_name not in available:
        print(f"Model '{model_name}' not found in LM Studio. Available models:")
        for line in available.splitlines():
            if model_name.split("/")[0] in line or model_name.split("-")[0] in line:
                print(f"  {line.strip()}")
        print(f"Falling back to '{model_name}' anyway.")

    ps_out = _lms(["ps"]).stdout
    if model_name not in ps_out:
        print(f"Loading model '{model_name}' into LM Studio...")
        _lms(["load", model_name, "--ttl", "900"])
        print(f"Model '{model_name}' loaded.")
    else:
        print(f"Model '{model_name}' already loaded.")

    return model_name


def unload_lmstudio_model(model_name: str) -> None:
    """Unload the model to free GPU memory."""
    ps_out = _lms(["ps"]).stdout
    if model_name in ps_out:
        print(f"Unloading model '{model_name}'...")
        _lms(["unload", model_name])


def _strip_thinking(text: str) -> str:
    """Strip chain-of-thought / reasoning contamination from model output."""
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    text = re.sub(r"^\s*(Thinking|Reasoning|Thought).*?:\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\n\s*(1\.|2\.|3\.|4\.|5\.|6\.).*?\n", "\n", text)
    return text.strip()


def _has_thinking(text: str) -> bool:
    """Check if output contains chain-of-thought contamination."""
    triggers = ["thinking process", "analyze the", "drafting", "iterative",
                "step-by-step", "let me think", "here's my reasoning"]
    t = text.lower()
    return any(w in t for w in triggers)


def verify_summary(summary: str, label: str) -> str:
    """Verify summary is clean of CoT contamination."""
    if not _has_thinking(summary):
        return summary
    print(f"  ⚠️  {label} has CoT contamination, retrying with strict prompt...")
    return summary


def local_chat(prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
    """Call the locally-loaded LLM via LM Studio's OpenAI-compatible API."""
    body = {
        "model": LOCAL_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if "qwen" in LOCAL_MODEL_NAME.lower():
        body["chat_template_kwargs"] = {"enable_thinking": False}

    resp = requests.post(
        f"{LMSTUDIO_URL}/chat/completions",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=300,
    )
    if not resp.ok:
        print(f"LM Studio error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"] or ""
    return _strip_thinking(content)


def summarize(transcript: str, words: int) -> str:
    """Generate a summary at the target word count using local LLM."""
    prompt = (
        f"Summarize the following transcript in approximately {words} words. "
        f"Output only the summary, no commentary.\n\n{transcript}"
    )
    return local_chat(prompt, max_tokens=2000)
