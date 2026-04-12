import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.hypothesis_maker_config.json')

DEFAULT_CONFIG = {
    'api_provider': 'claude',
    'api_key': '',
    'model': '',
    'last_folder': '',
    'last_ref_folder': '',
    'last_output': '',
}

DEFAULT_MODELS = {
    'claude': 'claude-sonnet-4-6',
    'openai': 'gpt-4o',
    'gemini': 'gemini-2.5-flash',
    'openrouter': 'nvidia/nemotron-3-super-120b-a12b:free',
}

# OpenRouter 무료 모델 fallback 체인 — 하나가 죽으면 다음 모델로 자동 전환
OPENROUTER_FREE_MODELS = [
    'nvidia/nemotron-3-super-120b-a12b:free',
    'qwen/qwen3-coder:free',
    'nousresearch/hermes-3-llama-3.1-405b:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'google/gemma-4-31b-it:free',
    'minimax/minimax-m2.5:free',
]

MODEL_OPTIONS = {
    'claude': [
        'claude-opus-4-6',
        'claude-sonnet-4-6',
        'claude-haiku-4-5-20251001',
        'claude-3-5-sonnet-20241022',
        'claude-3-5-haiku-20241022',
        'claude-3-opus-20240229',
    ],
    'openai': [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
        'gpt-4',
        'o1',
        'o1-mini',
        'o3-mini',
    ],
    'gemini': [
        'gemini-2.5-pro',
        'gemini-2.5-flash',
    ],
    'openrouter': OPENROUTER_FREE_MODELS,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
