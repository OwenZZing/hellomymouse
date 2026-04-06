"""Style constants for the Word report."""

FONT_NAME = '맑은 고딕'

# Colors (RGB tuples)
COLOR_PRIMARY    = (0, 70, 127)
COLOR_SECONDARY  = (60, 60, 60)
COLOR_MUTED      = (100, 100, 100)
COLOR_EASY_FC    = (0, 128, 0)
COLOR_MEDIUM_FC  = (180, 130, 0)
COLOR_HARD_FC    = (180, 0, 0)
COLOR_WARN       = (180, 60, 60)
COLOR_GREEN_MSG  = (0, 100, 60)
COLOR_GREEN_TEXT = (30, 80, 50)
COLOR_TREND      = (150, 80, 0)
COLOR_STARS_HIGH = (180, 130, 0)
COLOR_STARS_LOW  = (120, 120, 120)
COLOR_ATTRIBUTION = (160, 160, 160)
COLOR_LEGEND     = (80, 80, 80)
COLOR_TIME_NOTE  = (140, 100, 0)

# Cell background hex colors
BG_EASY   = 'C6EFCE'
BG_MEDIUM = 'FFEB9C'
BG_HARD   = 'FFC7CE'
BG_TREND  = 'FFF2CC'
BG_ALT    = 'EEF3F8'
BG_HEADER = (0, 70, 127)  # RGB for table header

FEAS_COLORS = {'Easy & Fast': BG_EASY, 'Medium': BG_MEDIUM, 'Hard': BG_HARD}
FEAS_FC     = {'Easy & Fast': COLOR_EASY_FC, 'Medium': COLOR_MEDIUM_FC, 'Hard': COLOR_HARD_FC}

COST_COLORS = {'Low': BG_EASY, 'Medium': BG_MEDIUM, 'High': BG_HARD}

STAR_LEGEND = [
    ('★☆☆☆☆', '졸업 아슬아슬, 심사위원에 많이 깎임'),
    ('★★☆☆☆', '졸업 무난, 취직은 다른 스펙이 받쳐줘야 함'),
    ('★★★☆☆', '졸업 안정적, 취직 시 논문으로 설명 가능'),
    ('★★★★☆', '졸업 오래 걸릴 수 있음. 끝나면 포지션 골라감'),
    ('★★★★★', '분야를 바꾸는 논문. 5년이 넘어도 worth it'),
]

ENCOURAGE_MSG = (
    '처음부터 과학계에 대단한 기여를 하려고 하지 마세요. 논문은 항상 지금까지 쌓인 지식과 한계점, '
    '그리고 다음 방향을 담고 있습니다. 이 프로그램은 단순히 그것을 정리했을 뿐입니다. '
    '명심하세요 — 논문 하나에는 반드시 한계가 있고, 여러분은 거기서 딱 한 발자국만 내딛으면 됩니다. '
    '이 리포트는 이 분야에 처음 오신 분을 위한 스타터팩입니다. '
    '더 깊은 가설의 발전은 반드시 지도교수님과 함께하세요.'
)
