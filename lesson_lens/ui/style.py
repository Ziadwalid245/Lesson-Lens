"""The look of the app: calm, light, big obvious buttons."""

GREEN = "#1f7a4d"
RED = "#c0392b"
METER_FILL = "#2e9e5b"
METER_TRACK = "#e3e6ea"

STYLESHEET = f"""
QWidget {{ font-family: "Segoe UI"; font-size: 10.5pt; color: #1f2328; }}
QMainWindow, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: #f6f7f9; }}
QFrame#card {{ background: white; border: 1px solid #e3e6ea; border-radius: 10px; }}
QFrame#card QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 18pt; font-weight: 600; }}
QLabel#subtitle, QLabel#hint {{ color: #5b6470; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; }}
QLabel#timer {{ font-size: 26pt; font-weight: 600; }}
QLabel#recDot {{ color: {RED}; font-size: 14pt; }}
QLabel#banner {{ background: #fff4ce; border: 1px solid #f0d27a; border-radius: 6px; padding: 8px 10px; }}
QLabel#errorBox {{ background: #fdecea; border: 1px solid #f5c2bd; border-radius: 6px; padding: 10px; }}
QLabel#okBox {{ background: #e7f5ec; border: 1px solid #b7dfc6; border-radius: 6px; padding: 8px 10px; }}

QPushButton {{ padding: 7px 14px; border-radius: 6px; border: 1px solid #cfd4da; background: white; }}
QPushButton:hover {{ background: #f0f2f4; }}
QPushButton:disabled {{ color: #9aa1a9; }}
QPushButton#primary {{ background: {GREEN}; color: white; border: none; font-size: 12.5pt; font-weight: 600; padding: 11px 26px; }}
QPushButton#primary:hover {{ background: #196640; }}
QPushButton#primary:disabled {{ background: #9cc7b1; color: white; }}
QPushButton#danger {{ background: {RED}; color: white; border: none; font-size: 12.5pt; font-weight: 600; padding: 11px 26px; }}
QPushButton#danger:hover {{ background: #a93226; }}
QPushButton#danger:disabled {{ background: #e3a59e; color: white; }}
QPushButton#link {{ border: none; background: transparent; color: #1a5fb4; padding: 2px; text-decoration: underline; }}

QComboBox, QLineEdit, QPlainTextEdit, QTableWidget {{ background: white; border: 1px solid #cfd4da; border-radius: 6px; padding: 4px; }}
QComboBox {{ padding: 6px 8px; min-height: 22px; }}
QHeaderView::section {{ background: #f0f2f4; border: none; border-bottom: 1px solid #e3e6ea; padding: 6px; font-weight: 600; }}
QTableWidget {{ gridline-color: #eceef1; }}
QProgressBar {{ border: none; background: {METER_TRACK}; border-radius: 4px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
"""
