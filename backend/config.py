DEFAULT_MODELS = {
    'claude': 'claude-sonnet-4-6',
    'openai': 'gpt-5-mini',
    'gemini': 'gemini-3.6-flash',
    'openrouter': 'openrouter/free',
}

# OpenRouter 무료 모델 fallback 체인 — 하나가 죽으면 다음 모델로 자동 전환
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
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-3.1-pro-preview',
    ],
    'openrouter': OPENROUTER_FREE_MODELS,
}
