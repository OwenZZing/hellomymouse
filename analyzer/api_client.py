"""Unified AI API client supporting Claude, OpenAI, Gemini, and OpenRouter."""
from __future__ import annotations
import time
from config import DEFAULT_MODELS, OPENROUTER_FREE_MODELS


class APIClient:
    def __init__(self, provider: str, api_key: str, model: str = ''):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model or DEFAULT_MODELS.get(self.provider, '')

        if self.provider == 'claude':
            self._init_claude()
        elif self.provider == 'openai':
            self._init_openai()
        elif self.provider == 'gemini':
            self._init_gemini()
        elif self.provider == 'openrouter':
            self._init_openrouter()
        else:
            raise ValueError(f'Unknown provider: {provider}')

    def _init_claude(self):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError('anthropic package not installed. Run: pip install anthropic')

    def _init_openai(self):
        try:
            import openai
            self._client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError('openai package not installed. Run: pip install openai')

    def _init_openrouter(self):
        try:
            import openai
            self._client = openai.OpenAI(
                base_url='https://openrouter.ai/api/v1',
                api_key=self.api_key,
            )
        except ImportError:
            raise ImportError('openai package not installed. Run: pip install openai')

    def _init_gemini(self):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            self._client = genai.GenerativeModel(self.model)
        except ImportError:
            raise ImportError('google-generativeai not installed. Run: pip install google-generativeai')

    # Per-model safe output token caps
    _MAX_TOKENS = {
        # Claude 4
        'claude-opus-4-7':              32000,
        'claude-opus-4-6':              32000,
        'claude-sonnet-4-6':            16000,
        # Claude 3.5
        'claude-3-5-sonnet-20241022':    8192,
        'claude-3-5-haiku-20241022':     8192,
        # Claude 3
        'claude-3-opus-20240229':        4096,
        'claude-haiku-4-5-20251001':     8192,
        # OpenAI
        'gpt-5.5':                      16384,
        'gpt-4o':                       16384,
        'gpt-4o-mini':                  16384,
        'gpt-4-turbo':                   4096,
        'gpt-4':                         4096,
        'o1':                           32768,
        'o1-mini':                      65536,
        'o3-mini':                      65536,
        # Gemini
        'gemini-2.5-pro':                8192,
        'gemini-2.5-flash':              8192,
    }

    def call(self, user_prompt: str, system_prompt: str = '', max_tokens: int = 4096) -> str:
        """Send prompt and return response text."""
        safe_max = self._MAX_TOKENS.get(self.model, max_tokens)
        max_tokens = min(max_tokens, safe_max)
        if self.provider == 'claude':
            return self._call_claude(user_prompt, system_prompt, max_tokens)
        elif self.provider == 'openai':
            return self._call_openai(user_prompt, system_prompt, max_tokens)
        elif self.provider == 'gemini':
            return self._call_gemini(user_prompt, system_prompt, max_tokens)
        elif self.provider == 'openrouter':
            return self._call_openrouter(user_prompt, system_prompt, max_tokens)

    def _call_claude(self, user_prompt: str, system_prompt: str, max_tokens: int) -> str:
        import anthropic
        kwargs = {
            'model': self.model,
            'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': user_prompt}],
        }
        if system_prompt:
            kwargs['system'] = system_prompt
        try:
            response = self._client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.AuthenticationError:
            raise ValueError('Claude API 키가 올바르지 않습니다.')
        except anthropic.RateLimitError:
            raise RuntimeError('Claude API rate limit에 도달했습니다. 잠시 후 다시 시도하세요.')
        except Exception as e:
            raise RuntimeError(f'Claude API 오류: {e}')

    def _call_openai(self, user_prompt: str, system_prompt: str, max_tokens: int) -> str:
        import openai
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': user_prompt})
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except openai.AuthenticationError:
            raise ValueError('OpenAI API 키가 올바르지 않습니다.')
        except openai.RateLimitError:
            raise RuntimeError('OpenAI API rate limit에 도달했습니다. 잠시 후 다시 시도하세요.')
        except Exception as e:
            raise RuntimeError(f'OpenAI API 오류: {e}')

    def _call_openrouter(self, user_prompt: str, system_prompt: str, max_tokens: int) -> str:
        """OpenRouter 무료 모델 fallback 체인으로 호출."""
        import openai

        # 현재 모델을 첫 번째로 시도하고, 나머지 fallback 모델 순회
        models_to_try = [self.model]
        for m in OPENROUTER_FREE_MODELS:
            if m != self.model:
                models_to_try.append(m)

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': user_prompt})

        last_error = None
        for model in models_to_try:
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except openai.AuthenticationError:
                raise ValueError(
                    'OpenRouter API 키가 올바르지 않습니다. '
                    'openrouter.ai → Keys에서 발급한 키인지 확인하세요.'
                )
            except (openai.RateLimitError, openai.NotFoundError) as e:
                last_error = e
                time.sleep(2)
                continue
            except Exception as e:
                last_error = e
                time.sleep(1)
                continue

        raise RuntimeError(
            f'OpenRouter 무료 모델이 모두 실패했습니다. '
            f'잠시 후 다시 시도하세요. (마지막 오류: {last_error})'
        )

    def _call_gemini(self, user_prompt: str, system_prompt: str, max_tokens: int) -> str:
        try:
            full_prompt = f'{system_prompt}\n\n{user_prompt}' if system_prompt else user_prompt
            response = self._client.generate_content(
                full_prompt,
                generation_config={'max_output_tokens': max_tokens},
                safety_settings=getattr(self, '_safety_settings', None),
            )
            # finish_reason 2 = SAFETY block
            if not response.candidates:
                raise RuntimeError('Gemini 안전 필터에 의해 응답이 차단됐습니다. Claude 또는 OpenAI 모델을 사용해보세요.')
            candidate = response.candidates[0]
            if candidate.finish_reason == 2:
                raise RuntimeError('Gemini 안전 필터에 의해 응답이 차단됐습니다. Claude 또는 OpenAI 모델을 사용해보세요.')
            return response.text
        except Exception as e:
            err = str(e).lower()
            if 'api_key' in err or 'authentication' in err or 'api key not valid' in err or 'invalid api key' in err:
                raise ValueError(
                    'Gemini API 키가 올바르지 않습니다. '
                    'aistudio.google.com → Get API Key에서 발급한 키인지 확인하세요.'
                )
            raise RuntimeError(f'Gemini API 오류: {e}')
