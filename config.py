import json
import os

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.hypothesis_maker_config.json')
KEYRING_SERVICE = 'HypothesisMaker'

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
    'openai': 'gpt-5-mini',
    'gemini': 'gemini-2.5-flash',
    'openrouter': 'openrouter/free',
}

OPENROUTER_FREE_MODELS = [
    'openrouter/free',
    'deepseek/deepseek-v4-flash:free',
    'nvidia/nemotron-3-super-120b-a12b:free',
    'qwen/qwen3-next-80b-a3b-instruct:free',
    'openai/gpt-oss-120b:free',
    'google/gemma-4-31b-it:free',
    'minimax/minimax-m2.5:free',
]

MODEL_OPTIONS = {
    'claude': [
        'claude-opus-4-7',
        'claude-sonnet-4-6',
        'claude-haiku-4-5-20251001',
    ],
    'openai': [
        'gpt-5.2',
        'gpt-5-mini',
        'gpt-5-nano',
        'gpt-4o',
    ],
    'gemini': [
        'gemini-3-flash-preview',
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
    ],
    'openrouter': OPENROUTER_FREE_MODELS,
}


def get_api_key(provider: str) -> str:
    if not _KEYRING_AVAILABLE or not provider:
        return ''
    try:
        return keyring.get_password(KEYRING_SERVICE, provider) or ''
    except Exception:
        return ''


def set_api_key(provider: str, key: str) -> None:
    if not _KEYRING_AVAILABLE or not provider:
        return
    try:
        if key:
            keyring.set_password(KEYRING_SERVICE, provider, key)
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, provider)
            except Exception:
                pass
    except Exception:
        pass


def _migrate_plaintext_key(data: dict) -> dict:
    plaintext = data.get('api_key', '')
    provider = data.get('api_provider', '')
    if plaintext and provider and _KEYRING_AVAILABLE:
        try:
            if not get_api_key(provider):
                set_api_key(provider, plaintext)
        except Exception:
            pass
        data['api_key'] = ''
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return data


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data = _migrate_plaintext_key(data)
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(data)
            provider = cfg.get('api_provider', '')
            if provider:
                cfg['api_key'] = get_api_key(provider)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    provider = cfg.get('api_provider', '')
    key = cfg.get('api_key', '')
    if provider and key:
        set_api_key(provider, key)
    try:
        to_save = dict(cfg)
        to_save['api_key'] = ''
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
