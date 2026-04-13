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
    ],
    'openai': [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
        'o1-mini',
    ],
    'gemini': [
        'gemini-2.5-flash',
    ],
    'openrouter': OPENROUTER_FREE_MODELS,
}
