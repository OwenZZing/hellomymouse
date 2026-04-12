DEFAULT_MODELS = {
    'claude': 'claude-sonnet-4-6',
    'openai': 'gpt-4o',
    'gemini': 'gemini-2.5-flash',
    # OpenRouter: OpenAI-compatible gateway to many models.
    # Default: DeepSeek Chat — very cheap, good at JSON-structured output.
    'openrouter': 'deepseek/deepseek-chat',
}

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
    # OpenRouter lets users type any model ID from openrouter.ai/models.
    # This list is just a curated starting set.
    'openrouter': [
        'deepseek/deepseek-chat',
        'deepseek/deepseek-r1',
        'meta-llama/llama-3.3-70b-instruct',
        'qwen/qwen-2.5-72b-instruct',
    ],
}
