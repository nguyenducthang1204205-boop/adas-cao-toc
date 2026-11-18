"""Widget của màn hình giám sát (chia theo vùng: nền chung, vùng video, cột phải, thẻ dưới)."""

from gui.widgets.common import (  # noqa: F401
    icon_html, set_icon, fit_to_screen, repolish, muted, ImageView, Card,
)
from gui.widgets.stage import (  # noqa: F401
    WelcomePanel, VideoStage, PlayBar,
)
from gui.widgets.panels import (  # noqa: F401
    SPEED_STEPS, DistanceGauge, StatusCard, perf_text, SpeedPanel, ConditionPanel,
)
from gui.widgets.tabs import (  # noqa: F401
    ChatPanel, LEVEL_TEXT_VI, LEVEL_COLOR, EventLog,
)

__all__ = [
    'icon_html', 'set_icon', 'fit_to_screen', 'repolish', 'muted', 'ImageView', 'Card', 'WelcomePanel',
    'VideoStage', 'PlayBar', 'SPEED_STEPS', 'DistanceGauge', 'StatusCard', 'perf_text', 'SpeedPanel',
    'ConditionPanel', 'ChatPanel', 'LEVEL_TEXT_VI', 'LEVEL_COLOR', 'EventLog',
]
