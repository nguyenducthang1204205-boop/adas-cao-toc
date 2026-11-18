"""
Định dạng số kiểu Việt Nam (dấu phẩy thập phân) - dùng chung cho lõi, giao diện và câu trả lời
của trợ lý; giống vn() / vnNum() / vnFactor() của app mobile.
"""


def vn(v: float, digits: int = 1) -> str:
    """Số thập phân kiểu Việt Nam: dấu phẩy ("39,7")."""
    return f"{v:.{digits}f}".replace(".", ",")


def vn_num(v: float) -> str:
    """Số kiểu Việt Nam, bỏ phần thập phân bằng 0: 2 · 2,5 · 1,15 (giống vnNum của app mobile)."""
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def vn_factor(v: float) -> str:
    """Hệ số nhân: tối đa 2 chữ số thập phân, bỏ số 0 thừa (1,0 · 1,4 · 1,15)."""
    s = f"{v:.2f}"
    if s.endswith("0"):
        s = s[:-1]
    return s.replace(".", ",")
