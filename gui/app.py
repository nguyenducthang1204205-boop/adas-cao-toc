"""Khởi tạo ứng dụng Qt và mở cửa sổ giám sát."""

import sys
from typing import Optional

INSTANCE_KEY = "adas-highway-safety-single-instance"


def _single_instance():
    """Trả về QLocalServer nếu đây là phiên bản đầu tiên, None nếu đã có phiên bản khác đang chạy."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.disconnectFromServer()
        return None
    # Không kết nối được: tên còn sót lại từ lần chạy bị treo/tắt ngang thì dọn đi
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.listen(INSTANCE_KEY)
    return server


def run(source: Optional[str] = None) -> int:
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    from adas.config import AppConfig
    from gui.main_window import MainWindow
    from gui.rendering import ensure_fonts, icon
    from gui.styles import STYLESHEET

    # Ô nhập số dùng dấu phẩy thập phân (2,5 giây) như vn() và app mobile
    QLocale.setDefault(QLocale(QLocale.Language.Vietnamese, QLocale.Country.Vietnam))
    app = QApplication(sys.argv)
    app.setApplicationName("ADAS Highway Safety")
    ensure_fonts()                       # Be Vietnam Pro + Material Icons (assets/fonts) - giống bản mobile
    app.setWindowIcon(icon("directions_car_outlined", "accent", 64))
    app.setStyleSheet(STYLESHEET)

    # Chỉ cho chạy một cửa sổ: lần chạy sau gửi tín hiệu để đưa cửa sổ cũ lên trước rồi thoát
    server = _single_instance()
    if server is None:
        print("Ứng dụng đang chạy - đưa cửa sổ hiện có lên trước.")
        return 0

    cfg = AppConfig.load()
    win = MainWindow(cfg, initial_source=source)

    def _raise_window():
        while server.hasPendingConnections():
            server.nextPendingConnection().close()
        if win.isMinimized():
            win.showNormal()
        win.raise_()
        win.activateWindow()

    server.newConnection.connect(_raise_window)
    win.show()
    if source:
        win.start()
    return app.exec()
