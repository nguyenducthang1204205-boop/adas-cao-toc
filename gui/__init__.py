"""
Tầng GUI (PySide6): cửa sổ giám sát, hộp thoại, luồng xử lý nền và lớp vẽ.

    app.py          khởi tạo QApplication (font, locale, stylesheet, một phiên bản duy nhất)
    main_window.py  cửa sổ chính - điều phối nguồn, luồng xử lý, trợ lý, nhật ký
    worker.py       QThread: đọc nguồn -> ADASPipeline -> vẽ -> ghi CSDL / video
    dialogs/        nguồn video, căn chỉnh camera (IPM), cài đặt ngưỡng, nhật ký vi phạm
    widgets/        các vùng của màn hình giám sát
    rendering/      lớp phủ cảnh báo + Bird's-Eye View bằng QPainter (vẽ được tiếng Việt)
    theme.py        token thiết kế "Night Drive" (dùng chung với app Android)
    styles.py       stylesheet Qt sinh từ token
"""
