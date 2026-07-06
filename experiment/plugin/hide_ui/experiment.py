"""Experiment gateway shown before Krita becomes usable.

Login and consent are full standalone windows (not dialog popups). Krita stays
completely hidden until the participant finishes every required step.
"""

import os
import csv
import json
import base64
import hashlib
import datetime
import traceback

from PyQt5.QtCore import Qt, QEventLoop, QTimer, QBuffer
from PyQt5.QtGui import QImage, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QWidget, QTextEdit,
    QApplication, QFrame, QScrollArea)

from .ui_controls import WhiteDotToggle

BASE_DIR = os.path.expanduser("~/krita_experiment_data")
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PASSWORDS_FILE = os.path.join(PLUGIN_DIR, "passwords.json")
CONSENT_FILE = os.path.join(PLUGIN_DIR, "consent.txt")
LOG = os.path.expanduser("~/krita_hide_ui_log.txt")

CONDITIONS = ["A", "B", "C"]
# Valid sessions per condition (password = condition + session, e.g. A1, B4).
CONDITION_SESSIONS = {
    "A": ["1", "2"],
    "B": ["1", "2"],
    "C": ["1", "2"],
}

# Standalone window on top of everything (incl. Krita splash).
_WINDOW_FLAGS = (
    Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint
    | Qt.WindowStaysOnTopHint
)

# Krita top-level windows that must stay hidden during the gateway.
_KRITA_TOPLEVEL = ("KisSplashScreen", "KisMainWindow")


def _log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def suppress_krita_ui(keep=None):
    """Hide Krita splash/main windows so the gateway is never covered."""
    try:
        for w in QApplication.topLevelWidgets():
            if w is keep:
                continue
            cls = w.metaObject().className()
            if cls in _KRITA_TOPLEVEL:
                w.hide()
                w.lower()
    except Exception:
        _log(traceback.format_exc())


def restore_krita_ui(qwin=None):
    """Ensure the main Krita window is visible after gateway / intro screens."""
    try:
        for w in QApplication.topLevelWidgets():
            if qwin is not None and w is not qwin:
                continue
            if w.metaObject().className() == "KisMainWindow":
                w.show()
                w.raise_()
                w.activateWindow()
                return True
    except Exception:
        _log(traceback.format_exc())
    return False


def _default_passwords_plain():
    plain = {}
    for c, sessions in CONDITION_SESSIONS.items():
        for s in sessions:
            plain["%s-%s" % (s, c)] = "%s%s" % (c, s)
    return plain


def _expected_password_keys():
    return set(_default_passwords_plain().keys())


def load_password_hashes():
    expected = _expected_password_keys()
    try:
        if os.path.exists(PASSWORDS_FILE):
            with open(PASSWORDS_FILE) as f:
                stored = json.load(f)
            if set(stored.keys()) == expected:
                return stored
    except Exception:
        _log(traceback.format_exc())
    plain = _default_passwords_plain()
    hashed = {k: _hash(v) for k, v in plain.items()}
    try:
        with open(PASSWORDS_FILE, "w") as f:
            json.dump(hashed, f, indent=2, sort_keys=True)
        _log("passwords.json updated: " + ", ".join(sorted(plain.values())))
    except Exception:
        _log(traceback.format_exc())
    return hashed


DEFAULT_CONSENT = """CONSENT TO PARTICIPATE IN RESEARCH

Study: Impact of changing the spatial configuration of commands on the
learning of software features.
Team: LOKI - Inria Centre at the University of Lille.

What you will do:
You will use a simplified version of the Krita drawing software to perform
a set of guided tasks. At certain points you will be asked to recall and
click on the location of specific commands as quickly as possible, and to
answer short questionnaires. The session is conducted remotely while you
share your screen with the experimenter.

Data:
Only quantitative interaction data is collected (timings, clicks, accuracy,
questionnaire answers) together with this signed consent. No sensitive or
medical data is collected. Your data is pseudonymised behind your
participant ID.

Voluntary participation:
Participation is voluntary and unpaid. You may stop at any time without
giving a reason.

By signing below, you confirm that you have read and understood the above
and that you agree to participate.

(This is placeholder text - edit consent.txt in the plugin folder to use
your final approved consent wording.)
"""


def load_consent():
    try:
        if os.path.exists(CONSENT_FILE):
            with open(CONSENT_FILE) as f:
                return f.read()
    except Exception:
        _log(traceback.format_exc())
    try:
        with open(CONSENT_FILE, "w") as f:
            f.write(DEFAULT_CONSENT)
    except Exception:
        _log(traceback.format_exc())
    return DEFAULT_CONSENT


class GatewayWindow(QWidget):
    """Base for unskippable standalone gateway windows."""

    def __init__(self, title):
        super().__init__(None)
        self.setWindowTitle(title)
        self.setWindowFlags(_WINDOW_FLAGS)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._loop = None
        self._result = None

        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #e0e0e0; }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #3c3c3c; color: #e0e0e0;
                border: 1px solid #555; padding: 4px;
            }
            QPushButton {
                background-color: #4a6fa5; color: white;
                border: none; padding: 8px 20px; min-width: 90px;
            }
            QPushButton:hover { background-color: #5a7fb5; }
            QPushButton#quitBtn {
                background-color: #555; color: #e0e0e0;
            }
            QPushButton#quitBtn:hover { background-color: #666; }
        """)

    def _finish(self, result):
        self._result = result
        self.hide()
        if self._loop is not None:
            self._loop.quit()

    def closeEvent(self, event):
        # No close button, but handle platform shortcuts (Cmd+W etc.).
        self._finish(None)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def _center_on_screen(self):
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2)

    def run_blocking(self):
        """Show this window and block until _finish() is called."""
        loop = QEventLoop()
        self._loop = loop

        # Keep Krita splash/main hidden while this window is open.
        guard = QTimer()
        guard.setInterval(100)
        guard.timeout.connect(lambda: suppress_krita_ui(self))
        guard.start()

        self._center_on_screen()
        suppress_krita_ui(self)
        self.show()
        self.raise_()
        self.activateWindow()
        loop.exec_()

        guard.stop()
        self._loop = None
        return self._result


class SignatureCanvas(QWidget):
    def __init__(self, parent=None, width=520, height=180):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._img = QImage(width, height, QImage.Format_RGB32)
        self._img.fill(Qt.white)
        self._last = None
        self.has_signed = False
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet("background-color: white; border: 1px solid #888;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(0, 0, self._img)

    def mousePressEvent(self, event):
        self._last = event.pos()
        self.has_signed = True

    def mouseMoveEvent(self, event):
        if self._last is not None:
            painter = QPainter(self._img)
            pen = QPen(QColor(0, 0, 0), 3, Qt.SolidLine, Qt.RoundCap,
                       Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self._last, event.pos())
            painter.end()
            self._last = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self._last = None

    def clear(self):
        self._img.fill(Qt.white)
        self.has_signed = False
        self.update()

    def to_base64_png(self):
        """Encode signature as base64 text (not saved as an image file)."""
        buf = QBuffer()
        buf.open(QBuffer.ReadWrite)
        self._img.save(buf, "PNG")
        return base64.b64encode(bytes(buf.data())).decode("ascii")


class LoginWindow(GatewayWindow):

    def __init__(self, password_hashes):
        super().__init__("Experiment Login")
        self._hashes = password_hashes

        title = QLabel("Software Learning Study")
        f = title.font()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Please enter your details to begin.\n"
            "You cannot use the software until this step is completed.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color:#aaa;")

        self.pid = QLineEdit()
        self.pid.setPlaceholderText("e.g. P07")
        self.condition = QComboBox()
        self.condition.addItems(CONDITIONS)
        self.session = QComboBox()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Provided by the experimenter")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow("Participant ID:", self.pid)
        form.addRow("Condition:", self.condition)
        form.addRow("Session:", self.session)
        form.addRow("Password:", self.password)

        self._update_sessions()
        self.condition.currentIndexChanged.connect(self._update_sessions)

        self.msg = QLabel("")
        self.msg.setStyleSheet("color:#e06c6c;")
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignCenter)

        self.startBtn = QPushButton("Start")
        self.startBtn.setDefault(True)
        self.quitBtn = QPushButton("Quit")
        self.quitBtn.setObjectName("quitBtn")
        btns = QHBoxLayout()
        btns.addWidget(self.quitBtn)
        btns.addStretch()
        btns.addWidget(self.startBtn)

        inner = QWidget()
        inner.setMaximumWidth(480)
        inner_lay = QVBoxLayout(inner)
        inner_lay.addWidget(title)
        inner_lay.addWidget(subtitle)
        inner_lay.addSpacing(16)
        inner_lay.addLayout(form)
        inner_lay.addWidget(self.msg)
        inner_lay.addSpacing(8)
        inner_lay.addLayout(btns)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()
        outer.addWidget(inner, alignment=Qt.AlignCenter)
        outer.addStretch()

        self.setMinimumSize(560, 420)

        self.startBtn.clicked.connect(self._try_start)
        self.quitBtn.clicked.connect(lambda: self._finish(None))
        self.password.returnPressed.connect(self._try_start)

    def _update_sessions(self):
        c = self.condition.currentText()
        sessions = CONDITION_SESSIONS.get(c, [])
        self.session.blockSignals(True)
        self.session.clear()
        self.session.addItems(sessions)
        self.session.blockSignals(False)

    def _try_start(self):
        pid = self.pid.text().strip()
        if not pid:
            self.msg.setText("Please enter your Participant ID.")
            return
        s = self.session.currentText()
        c = self.condition.currentText()
        key = "%s-%s" % (s, c)
        expected = self._hashes.get(key)
        if not expected or _hash(self.password.text()) != expected:
            self.msg.setText(
                "Incorrect password for this session/condition.")
            return
        self._finish({
            "participant_id": pid,
            "session": int(s),
            "condition": c,
        })


class ConsentWindow(GatewayWindow):

    def __init__(self, consent_text):
        super().__init__("Consent Form")
        self._signed_ok = False

        title = QLabel("Consent to Participate")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)

        notice = QLabel(
            "You must read, agree, and sign before you can use the software.")
        notice.setAlignment(Qt.AlignCenter)
        notice.setStyleSheet("color:#aaa;")

        # --- Rules box (scrollable, fixed height) ---
        rules_label = QLabel("Onboarding rules")
        rules_label.setStyleSheet("font-weight: bold; color: #ccc;")

        rules_text = QTextEdit()
        rules_text.setReadOnly(True)
        rules_text.setPlainText(consent_text)
        rules_text.setFrameStyle(QFrame.NoFrame)

        rules_scroll = QScrollArea()
        rules_scroll.setWidget(rules_text)
        rules_scroll.setWidgetResizable(True)
        rules_scroll.setFixedHeight(280)
        rules_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #555; background: #3c3c3c; }")

        rules_box = QVBoxLayout()
        rules_box.setSpacing(6)
        rules_box.addWidget(rules_label)
        rules_box.addWidget(rules_scroll)

        rules_widget = QWidget()
        rules_widget.setLayout(rules_box)

        # --- Agreement checkbox: clearly BELOW the rules box ---
        self.agree = WhiteDotToggle()
        agree_text = QLabel(
            "I have read and understood the above and I agree to participate.")
        agree_text.setWordWrap(True)

        agree_row = QHBoxLayout()
        agree_row.setContentsMargins(0, 0, 0, 0)
        agree_row.addWidget(self.agree, alignment=Qt.AlignTop)
        agree_row.addWidget(agree_text, stretch=1)

        agree_widget = QWidget()
        agree_lay = QVBoxLayout(agree_widget)
        agree_lay.setContentsMargins(0, 12, 0, 12)
        agree_lay.addLayout(agree_row)

        # --- Signature section ---
        sig_label = QLabel("Please sign below using your mouse:")
        sig_label.setStyleSheet("font-weight: bold; color: #ccc;")

        self.canvas = SignatureCanvas(self)
        sig_row = QHBoxLayout()
        sig_row.addStretch()
        sig_row.addWidget(self.canvas)
        sig_row.addStretch()

        sig_widget = QWidget()
        sig_lay = QVBoxLayout(sig_widget)
        sig_lay.setContentsMargins(0, 0, 0, 0)
        sig_lay.setSpacing(8)
        sig_lay.addWidget(sig_label)
        sig_lay.addLayout(sig_row)

        self.msg = QLabel("")
        self.msg.setStyleSheet("color:#e06c6c;")
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignCenter)

        clearBtn = QPushButton("Clear signature")
        self.submitBtn = QPushButton("Sign & Continue")
        self.submitBtn.setDefault(True)
        btns = QHBoxLayout()
        btns.addWidget(clearBtn)
        btns.addStretch()
        btns.addWidget(self.submitBtn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(0)
        lay.addWidget(title)
        lay.addWidget(notice)
        lay.addSpacing(12)
        lay.addWidget(rules_widget)
        lay.addWidget(agree_widget)
        lay.addWidget(sig_widget)
        lay.addWidget(self.msg)
        lay.addSpacing(8)
        lay.addLayout(btns)

        self.setMinimumSize(700, 680)

        clearBtn.clicked.connect(self.canvas.clear)
        self.submitBtn.clicked.connect(self._submit)

    def _submit(self):
        if not self.agree.isChecked():
            self.msg.setText("You must check the agreement box to continue.")
            return
        if not self.canvas.has_signed:
            self.msg.setText("Please provide your signature before continuing.")
            return
        self._signed_ok = True
        self._finish(True)

    @property
    def signed_ok(self):
        return self._signed_ok


def _hide_krita(qwin):
    suppress_krita_ui()
    if qwin is not None:
        qwin.hide()
        qwin.lower()


def _show_krita(qwin):
    if qwin is not None:
        qwin.show()
        qwin.raise_()
        qwin.activateWindow()


def _save_session_record(pdir, info, ts):
    path = os.path.join(pdir, "sessions.csv")
    is_new = not os.path.exists(path)
    try:
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp", "participant_id", "session",
                            "condition", "consent_signed", "consent_record"])
            w.writerow([ts, info["participant_id"], info["session"],
                        info["condition"], info.get("consent_signed", ""),
                        info.get("consent_record", "")])
    except Exception:
        _log(traceback.format_exc())


def run_gateway(qwin):
    """Run login (+ consent on session 1). Krita stays hidden the whole time.
    Returns session info on success, or None if the participant quit."""
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        _hide_krita(qwin)

        hashes = load_password_hashes()
        info = LoginWindow(hashes).run_blocking()
        if info is None:
            return None
        _log("login ok: %s" % info)

        pdir = os.path.join(BASE_DIR, info["participant_id"])
        os.makedirs(pdir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if info["session"] == 1:
            try:
                consent_win = ConsentWindow(load_consent())
            except Exception:
                _log("ConsentWindow failed:\n" + traceback.format_exc())
                return None
            ok = consent_win.run_blocking()
            if not ok or not consent_win.signed_ok:
                return None
            record_path = os.path.join(pdir, "consent_%s.json" % ts)
            record = {
                "participant_id": info["participant_id"],
                "session": info["session"],
                "condition": info["condition"],
                "timestamp": ts,
                "agreed": True,
                "signature_base64": consent_win.canvas.to_base64_png(),
            }
            with open(record_path, "w") as f:
                json.dump(record, f, indent=2)
            info["consent_signed"] = True
            info["consent_record"] = record_path
            _log("consent saved to %s" % record_path)

        info["started_at"] = ts
        _save_session_record(pdir, info, ts)
        try:
            with open(os.path.join(BASE_DIR, "current_session.json"), "w") as f:
                json.dump(info, f, indent=2)
        except Exception:
            _log(traceback.format_exc())

        _log("gateway completed: %s" % info)
        return info
    except Exception:
        _log(traceback.format_exc())
        return None
