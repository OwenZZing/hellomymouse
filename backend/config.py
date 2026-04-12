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
    # This list mixes :free variants (no card required, tight rate limit)
    # and paid variants (very cheap, ~$0.05–0.2 per 5-paper run).
    'openrouter': [
        # ── Free tier (no payment, but ~50/day & 20/min limit) ──
        'meta-llama/llama-3.3-70b-instruct:free',
        'deepseek/deepseek-r1:free',
        'deepseek/deepseek-chat-v3-0324:free',
        # ── Paid (very cheap, no rate limit headaches) ──
        'deepseek/deepseek-chat',
        'deepseek/deepseek-r1',
        'meta-llama/llama-3.3-70b-instruct',
        'qwen/qwen-2.5-72b-instruct',
    ],
}
