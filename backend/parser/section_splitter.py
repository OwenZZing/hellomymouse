"""Split paper full text into sections by heading detection."""
from __future__ import annotations
import re

# Common academic section headings (case-insensitive)
SECTION_PATTERNS = [
    r'abstract',
    r'introduction',
    r'background',
    r'related\s+work',
    r'literature\s+review',
    r'methods?(?:\s+and\s+materials?)?',
    r'materials?\s+and\s+methods?',
    r'experimental\s+(?:setup|design|methods?)',
    r'system\s+(?:design|overview|model)',
    r'(?:proposed\s+)?(?:approach|framework|architecture|model)',
    r'results?',
    r'evaluation',
    r'experiments?',
    r'discussion',
    r'limitations?',
    r'(?:conclusion|concluding\s+remarks?)s?',
    r'future\s+(?:work|directions?)',
    r'acknowledgm?ents?',
    r'references',
]

_HEADING_RE = re.compile(
    r'(?:^|\n)\s*(?:\d+\.?\s+)?(' + '|'.join(SECTION_PATTERNS) + r')[\s\n:—\-]*',
    re.IGNORECASE | re.MULTILINE
)


def split_sections(full_text: str) -> dict[str, str]:
    """
    Detect section headings in full_text and split into sections.
    Returns dict mapping section_name (lowercase) -> section_content.
    If no headings found, returns {'full': full_text}.
    """
    matches = list(_HEADING_RE.finditer(full_text))

    if not matches:
        return {'full': full_text}

    sections: dict[str, str] = {}

    # Text before first heading
    if matches[0].start() > 0:
        preamble = full_text[:matches[0].start()].strip()
        if preamble:
            sections['preamble'] = preamble

    for i, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        # Normalize heading
        heading = re.sub(r'\s+', ' ', heading)

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = full_text[start:end].strip()

        # If duplicate heading, append index
        if heading in sections:
            heading = f'{heading}_{i}'

        sections[heading] = content

    return sections


def get_key_sections(sections: dict[str, str], max_chars: int = 8000) -> str:
    """
    Extract the most relevant sections for hypothesis generation:
    methods, results, discussion, limitations, future work, conclusion.
    Concatenated and truncated to max_chars total.
    """
    priority_keys = [
        'methods', 'materials and methods', 'experimental setup',
        'results', 'evaluation', 'experiments',
        'discussion', 'limitations', 'limitation',
        'future work', 'future directions', 'conclusion', 'conclusions',
        'full',
    ]

    selected = []
    total = 0
    used_keys = set()

    for pk in priority_keys:
        for k, v in sections.items():
            if pk in k and k not in used_keys:
                chunk = v[:max_chars // 4]
                selected.append(f'[{k.upper()}]\n{chunk}')
                total += len(chunk)
                used_keys.add(k)
                if total >= max_chars:
                    break
        if total >= max_chars:
            break

    # Fill remaining from other sections
    for k, v in sections.items():
        if k not in used_keys and total < max_chars:
            chunk = v[: max_chars - total]
            selected.append(f'[{k.upper()}]\n{chunk}')
            total += len(chunk)

    return '\n\n'.join(selected)[:max_chars]
