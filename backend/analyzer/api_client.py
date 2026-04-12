"""Unified AI API client supporting Claude, OpenAI, Gemini, and OpenRouter."""
from __future__ import annotations
import time
from config import DEFAULT_MODELS, OPENROUTER_FREE_MODELS

# Gemini models known to have stricter safety enforcement
_GEMINI_STRICT_MODELS = {'gemini-2.5-flash', 'gemini-2.5-pro'}
# Fallback model when a strict model gets safety-blocked
_GEMINI_FALLBACK_MODEL = 'gemini-2.5-flash'


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
            import httpx
            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url='https://openrouter.ai/api/v1',
                timeout=httpx.Timeout(300.0, connect=30.0),
                default_headers={
                    'HTTP-Referer': 'https://hellomymouse.com',
                    'X-Title': 'Hypothesis Maker',
                },
            )
        except ImportError:
            raise ImportError('openai package not installed. Run: pip install openai')

    def _init_gemini(self):
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=self.api_key)
            self._genai_types = types
            self._safety_settings = [
                types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_CIVIC_INTEGRITY', threshold='BLOCK_NONE'),
            ]
        except ImportError:
            raise ImportError('google-genai not installed. Run: pip install google-genai')

    def upload_files_for_gemini(self, file_paths: list) -> list:
        """Upload PDF files to Gemini File API. Returns list of file objects."""
        if self.provider != 'gemini':
            raise ValueError('File API는 Gemini 전용입니다.')
        uploaded = []
        for path in file_paths:
            try:
                f = self._client.files.upload(file=path)
                uploaded.append(f)
            except Exception as e:
                raise RuntimeError(f'Gemini 파일 업로드 실패 ({path}): {e}')
        return uploaded

    def call_with_files(self, user_prompt: str, system_prompt: str = '',
                        files: list = None, max_tokens: int = 4096) -> str:
        """Gemini File API를 이용한 호출. Gemini가 아닐 경우 일반 call()로 fallback."""
        if self.provider != 'gemini' or not files:
            return self.call(user_prompt, system_prompt, max_tokens)
        safe_max = self._MAX_TOKENS.get(self.model, max_tokens)
        max_tokens = min(max_tokens, safe_max)
        return self._call_gemini_with_files(user_prompt, system_prompt, files, max_tokens)

    # Per-model safe output token caps (match each model's actual limit)
    _MAX_TOKENS = {
        # Claude 4.x — Sonnet supports 64K, Opus/Haiku 32K
        'claude-opus-4-6':              32000,
        'claude-sonnet-4-6':            64000,
        'claude-haiku-4-5-20251001':    16000,
        # Claude 3.5
        'claude-3-5-sonnet-20241022':    8192,
        'claude-3-5-haiku-20241022':     8192,
        # Claude 3
        'claude-3-opus-20240229':        4096,
        # OpenAI
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
        # OpenRouter free models generally support 16K–32K output.
        # Use 16384 as a safe default for models not in the table.
        default_cap = 16384 if self.provider == 'openrouter' else max_tokens
        safe_max = self._MAX_TOKENS.get(self.model, default_cap)
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
        # Use streaming for ALL Claude calls. Non-streaming requests that may
        # exceed 10 minutes are rejected by the SDK with:
        #   "Streaming is required for operations that may take longer than 10 minutes"
        # This fires on Opus + large Stage 2 inputs (many papers) even though
        # most requests finish in under a minute. Streaming is safe either way.
        import anthropic
        kwargs = {
            'model': self.model,
            'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': user_prompt}],
        }
        if system_prompt:
            kwargs['system'] = system_prompt
        try:
            parts: list[str] = []
            with self._client.messages.stream(**kwargs) as stream:
                for delta in stream.text_stream:
                    parts.append(delta)
            return ''.join(parts)
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
            label = 'OpenRouter' if self.provider == 'openrouter' else 'OpenAI'
            raise ValueError(f'{label} API 키가 올바르지 않습니다.')
        except openai.RateLimitError:
            label = 'OpenRouter' if self.provider == 'openrouter' else 'OpenAI'
            hint = ' (무료 모델은 사용량 제한이 엄격합니다)' if self.provider == 'openrouter' else ''
            raise RuntimeError(f'{label} API rate limit에 도달했습니다. 잠시 후 다시 시도하세요.{hint}')
        except Exception as e:
            label = 'OpenRouter' if self.provider == 'openrouter' else 'OpenAI'
            raise RuntimeError(f'{label} API 오류: {e}')

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

    def _call_gemini_with_files(self, user_prompt: str, system_prompt: str,
                                files: list, max_tokens: int) -> str:
        return self._gemini_with_retry(user_prompt, system_prompt, max_tokens,
                                       files=files)

    def _is_safety_blocked(self, response) -> bool:
        """Check if a Gemini response was blocked by safety filters."""
        if not response.candidates:
            return True
        candidate = response.candidates[0]
        if candidate.finish_reason and candidate.finish_reason.name == 'SAFETY':
            return True
        return False

    def _gemini_generate(self, model: str, contents, max_tokens: int):
        """Low-level Gemini generate_content call."""
        types = self._genai_types
        return self._client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                safety_settings=self._safety_settings,
            ),
        )

    def _gemini_with_retry(self, user_prompt: str, system_prompt: str,
                           max_tokens: int, files: list = None) -> str:
        """Gemini call with safety-block retry: reframe prompt → fallback model."""
        academic_prefix = (
            "You are an academic research assistant. "
            "This is a scientific analysis task for academic purposes only.\n\n"
        )

        # Build contents
        if files:
            parts = []
            if system_prompt:
                parts.append(f"[SYSTEM]\n{academic_prefix}{system_prompt}\n\n[USER]\n")
            else:
                parts.append(f"[SYSTEM]\n{academic_prefix}\n\n[USER]\n")
            parts.extend(files)
            parts.append(user_prompt)
            contents = parts
        else:
            full_prompt = (f'{academic_prefix}{system_prompt}\n\n{user_prompt}'
                           if system_prompt else f'{academic_prefix}{user_prompt}')
            contents = full_prompt

        # Attempt 1: original model
        try:
            response = self._gemini_generate(self.model, contents, max_tokens)
            if not self._is_safety_blocked(response):
                return response.text
        except Exception as e:
            err = str(e).lower()
            if 'api_key' in err or 'authentication' in err or 'api key not valid' in err or 'invalid api key' in err:
                raise ValueError(
                    'Gemini API 키가 올바르지 않습니다. '
                    'aistudio.google.com → Get API Key에서 발급한 키인지 확인하세요.'
                )
            if 'safety' not in err and 'block' not in err and 'recitation' not in err:
                raise RuntimeError(f'Gemini API 오류: {e}')

        # Attempt 2: reframed prompt (add stronger academic context)
        reframe_prefix = (
            "IMPORTANT: This is a purely academic and scientific analysis. "
            "All content discussed is from published peer-reviewed research papers. "
            "The analysis is for educational purposes in a university research setting. "
            "Please analyze the following research content objectively.\n\n"
        )
        if files:
            parts_v2 = []
            sys_v2 = f"[SYSTEM]\n{reframe_prefix}{system_prompt}\n\n[USER]\n" if system_prompt else f"[SYSTEM]\n{reframe_prefix}\n\n[USER]\n"
            parts_v2.append(sys_v2)
            parts_v2.extend(files)
            parts_v2.append(user_prompt)
            contents_v2 = parts_v2
        else:
            contents_v2 = (f'{reframe_prefix}{system_prompt}\n\n{user_prompt}'
                           if system_prompt else f'{reframe_prefix}{user_prompt}')

        try:
            time.sleep(1)
            response = self._gemini_generate(self.model, contents_v2, max_tokens)
            if not self._is_safety_blocked(response):
                return response.text
        except Exception:
            pass  # Fall through to model fallback

        # Attempt 3: fallback to a less restrictive model
        if self.model in _GEMINI_STRICT_MODELS:
            try:
                time.sleep(1)
                response = self._gemini_generate(_GEMINI_FALLBACK_MODEL, contents_v2, max_tokens)
                if not self._is_safety_blocked(response):
                    return response.text
            except Exception:
                pass

        raise RuntimeError(
            'Gemini 안전 필터에 의해 응답이 반복 차단됐습니다. '
            'Claude 또는 OpenAI 모델을 사용해주세요.'
        )

    def _call_gemini(self, user_prompt: str, system_prompt: str, max_tokens: int) -> str:
        return self._gemini_with_retry(user_prompt, system_prompt, max_tokens)
