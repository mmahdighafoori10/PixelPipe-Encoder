APP_STYLE_SHEET = """
QWidget {
    color: #EAF3FF;
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 10pt;
}

QMainWindow, QDialog {
    background: #071426;
}

QFrame#surface, QGroupBox {
    background: #0D1D34;
    border: 1px solid #1D3656;
    border-radius: 14px;
}

QGroupBox {
    margin-top: 13px;
    padding: 18px 12px 12px 12px;
    font-weight: 650;
    color: #F6C75C;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}

QLabel#mutedLabel {
    color: #91A7C2;
}

QLabel#titleLabel {
    font-size: 24pt;
    font-weight: 750;
    color: #FFFFFF;
}

QLabel#sectionTitle {
    font-size: 13pt;
    font-weight: 700;
    color: #FFFFFF;
}

QLabel#statusReady {
    background: #123F3D;
    color: #74F0C1;
    border: 1px solid #216C62;
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 650;
}

QLabel#statusMissing {
    background: #472A22;
    color: #FFB39F;
    border: 1px solid #7C4637;
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 650;
}

QPushButton, QToolButton {
    min-height: 36px;
    padding: 0 14px;
    border: 1px solid #294665;
    border-radius: 10px;
    background: #132944;
    color: #EAF3FF;
    font-weight: 600;
}

QPushButton:hover, QToolButton:hover {
    background: #193755;
    border-color: #3C6C98;
}

QPushButton:pressed, QToolButton:pressed {
    background: #0C2038;
}

QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus {
    border: 2px solid #35B9FF;
}

QPushButton:disabled, QToolButton:disabled {
    color: #60758E;
    background: #102035;
    border-color: #1C3149;
}

QPushButton#primaryButton {
    background: #F3BC45;
    color: #13213A;
    border: 1px solid #FFD979;
    font-weight: 750;
}

QPushButton#primaryButton:hover {
    background: #FFD066;
}

QPushButton#dangerButton {
    color: #FFB6A7;
    border-color: #70443D;
    background: #392623;
}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    min-height: 36px;
    background: #09182B;
    border: 1px solid #294665;
    border-radius: 9px;
    padding: 0 10px;
    selection-background-color: #25689A;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: #10233C;
    border: 1px solid #355879;
    selection-background-color: #245A82;
    padding: 4px;
}

QCheckBox {
    spacing: 9px;
    color: #C8D7E9;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #416282;
    background: #09182B;
}

QCheckBox::indicator:checked {
    background: #35B9FF;
    border-color: #77D2FF;
}

QTableWidget {
    background: #0B1A2E;
    alternate-background-color: #0D2036;
    border: 1px solid #1D3656;
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: #1B476A;
    selection-color: #FFFFFF;
}

QHeaderView::section {
    background: #102640;
    color: #9BB2CB;
    border: none;
    border-bottom: 1px solid #27425E;
    padding: 10px 8px;
    font-weight: 650;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #142A43;
}

QProgressBar {
    min-height: 13px;
    background: #09182B;
    border: 1px solid #294665;
    border-radius: 7px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    border-radius: 6px;
    background: #35B9FF;
}

QScrollArea {
    border: none;
    background: #071426;
}

QWidget#settingsContent {
    background: #071426;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0;
}

QScrollBar::handle:vertical {
    background: #2A4865;
    min-height: 32px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QFrame#dropArea {
    background: #0A1B31;
    border: 2px dashed #315678;
    border-radius: 16px;
}

QFrame#dropArea:hover {
    border-color: #35B9FF;
    background: #0E2440;
}

QStatusBar {
    background: #08172A;
    color: #90A6BE;
    border-top: 1px solid #19314C;
}
"""
