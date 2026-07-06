"""Tutorial intro / hold screens for Session 1 and Session 2."""

import random
import traceback

from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QWidget, QApplication, QSizePolicy)

from .experiment import GatewayWindow, suppress_krita_ui, _log

TUTORIAL_LEARN_SEC = 600        # 10 min — Session 1 tutorials 2–3, all Session 2 tutorials
TUTORIAL_PRACTICE_SEC = 900     # 15 min — Session 1 practice trial only
BREAK_SEC = 10                  # 10 s break between blocks
TUTORIAL_1_TIME_SEC = TUTORIAL_PRACTICE_SEC
TUTORIAL_2_TIME_SEC = TUTORIAL_LEARN_SEC
TUTORIAL_3_TIME_SEC = TUTORIAL_LEARN_SEC
TUTORIAL_TIME_SEC = TUTORIAL_1_TIME_SEC

BREAK_MESSAGE = {
    "title": "Break",
    "body": (
        "This is a break.\n\n"
        "You can practise in Krita if you want, but you do not have to.\n\n"
        "The next block will start automatically when the timer ends."),
}


def session2_tutorial_count(condition):
    """Condition A: 2 tutorials; B and C: 3 tutorials."""
    return 2 if condition == "A" else 3


def learning_skip_password(condition, session, learn_num):
    """Experimenter skip password for a learning phase or its following break."""
    return "%s%sL%s" % (condition, session, int(learn_num))


def break_skip_password(condition, session, learn_num):
    """Same password as the learning block that preceded this break (e.g. A1L1)."""
    return learning_skip_password(condition, session, learn_num)


def recall_skip_password(condition, session, learn_num):
    """Same password as the learning block for this recall (e.g. A1L1)."""
    return learning_skip_password(condition, session, learn_num)


def _tutorial_time_label(seconds):
    if seconds % 60 == 0 and seconds >= 60:
        mins = seconds // 60
        return "%d minute%s" % (mins, "" if mins == 1 else "s")
    return "%d second%s" % (seconds, "" if seconds == 1 else "s")


def _learn_body(seconds, extra=""):
    base = (
        "Watch the tutorial video on the right.\n\n"
        "Mimic what you see in Krita. Use the same tools and actions.\n\n"
        "You will have %s to practice when the canvas opens."
        % _tutorial_time_label(seconds)
    )
    if extra:
        return extra + "\n\n" + base
    return base


TUTORIAL_1 = {
    "title": "Tutorial 1: Practice trial",
    "body": _learn_body(
        TUTORIAL_PRACTICE_SEC,
        "This first block is a practice trial. Your answers here are not recorded."),
    "logged": False,
    "learn_sec": TUTORIAL_PRACTICE_SEC,
}

TUTORIAL_2 = {
    "title": "Learning Tutorial 2",
    "body": _learn_body(TUTORIAL_LEARN_SEC),
    "logged": True,
    "learn_sec": TUTORIAL_LEARN_SEC,
}

TUTORIAL_3 = {
    "title": "Learning Tutorial 3",
    "body": _learn_body(TUTORIAL_LEARN_SEC),
    "logged": True,
    "learn_sec": TUTORIAL_LEARN_SEC,
}

SESSION_1_TUTORIALS = (TUTORIAL_1, TUTORIAL_2, TUTORIAL_3)

SESSION_2_OPENING_RECALL = {
    "title": "Recall: Layout A",
    "body": (
        "Before the new tutorials, you will take a recall test on the "
        "interface you learned in Session 1.\n\n"
        "Click each command location as quickly and accurately as you can."),
}

SESSION_2_TUTORIAL = {
    "title": "Learning Tutorial %d",
    "body": _learn_body(TUTORIAL_LEARN_SEC),
    "logged": True,
    "learn_sec": TUTORIAL_LEARN_SEC,
}

HOLD_AFTER_TUTORIAL = {
    1: {
        "title": "Tutorial 1 complete",
        "body": (
            "Nice work.\n\n"
            "When you press Continue, you will take a short recall test, "
            "then Learning Tutorial 2 will begin."),
    },
    2: {
        "title": "Tutorial 2 complete",
        "body": (
            "Nice work.\n\n"
            "When you press Continue, you will take a short recall test, "
            "then Learning Tutorial 3 will begin."),
    },
    3: {
        "title": "Tutorial 3 complete",
        "body": (
            "Nice work.\n\n"
            "When you press Continue, you will take a short recall test, "
            "then Session 1 will end."),
    },
}

HOLD_SESSION2_AFTER_TUTORIAL = {
    1: {
        "title": "Tutorial 1 complete",
        "body": (
            "Nice work.\n\n"
            "When you press Continue, you will take a short recall test, "
            "then the next tutorial will begin."),
    },
    2: {
        "title": "Tutorial 2 complete",
        "body": (
            "Nice work.\n\n"
            "When you press Continue, you will take a short recall test "
            "or finish with the survey."),
    },
}


class TutorialIntroWindow(GatewayWindow):
    """Full-screen gateway before each timed tutorial block."""

    def __init__(self, title, body):
        super().__init__(title)

        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setStyleSheet(
            "color: #ffffff; font-size: 22px; font-weight: bold; padding: 0 12px;")
        heading.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        continue_btn = QPushButton("Continue")
        continue_btn.setDefault(True)
        continue_btn.clicked.connect(lambda: self._finish(True))

        inner = QWidget()
        inner.setMinimumWidth(480)
        inner.setMaximumWidth(560)
        lay = QVBoxLayout(inner)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.addWidget(heading)
        lay.addSpacing(8)

        for para in body.strip().split("\n\n"):
            text = para.strip()
            if not text:
                continue
            desc = QLabel(text)
            desc.setWordWrap(True)
            desc.setAlignment(Qt.AlignCenter)
            desc.setStyleSheet(
                "color: #f2f2f2; font-size: 15px; padding: 4px 12px;")
            desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            lay.addWidget(desc)

        lay.addSpacing(20)
        lay.addWidget(continue_btn, alignment=Qt.AlignCenter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.addStretch(1)
        outer.addWidget(inner, 0, Qt.AlignCenter)
        outer.addStretch(1)

        inner.adjustSize()
        self.adjustSize()
        self.setMinimumSize(560, max(360, inner.sizeHint().height() + 140))


def run_tutorial_intro(title, body):
    """Show intro window; return True when the participant continues."""
    try:
        win = TutorialIntroWindow(title, body)
        suppress_krita_ui(win)
        return win.run_blocking() is True
    except Exception:
        _log(traceback.format_exc())
        return False


def run_hold_screen(title, body):
    """Transition screen between tutorial blocks."""
    return run_tutorial_intro(title, body)


class RecallScoreWindow(GatewayWindow):
    """Show recall score before continuing to the next study block."""

    def __init__(self, percent):
        super().__init__("Recall complete")
        pct = max(0, min(100, int(percent)))

        heading = QLabel("Recall complete")
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setStyleSheet(
            "color: #ffffff; font-size: 22px; font-weight: bold; padding: 0 12px;")

        score = QLabel("%d%%" % pct)
        score.setAlignment(Qt.AlignCenter)
        score.setStyleSheet(
            "color: #ffffff; font-size: 72px; font-weight: bold; padding: 8px 12px;")

        sub = QLabel("Your score")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #f2f2f2; font-size: 16px; padding: 4px 12px;")

        continue_btn = QPushButton("Continue")
        continue_btn.setDefault(True)
        continue_btn.clicked.connect(lambda: self._finish(True))

        inner = QWidget()
        inner.setMinimumWidth(480)
        inner.setMaximumWidth(560)
        lay = QVBoxLayout(inner)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.addWidget(heading)
        lay.addSpacing(12)
        lay.addWidget(score)
        lay.addWidget(sub)
        lay.addSpacing(24)
        lay.addWidget(continue_btn, alignment=Qt.AlignCenter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.addStretch(1)
        outer.addWidget(inner, 0, Qt.AlignCenter)
        outer.addStretch(1)

        inner.adjustSize()
        self.adjustSize()
        self.setMinimumSize(560, max(360, inner.sizeHint().height() + 140))


def run_recall_score_screen(percent):
    """Show recall score; return True when the participant continues."""
    try:
        win = RecallScoreWindow(percent)
        suppress_krita_ui(win)
        return win.run_blocking() is True
    except Exception:
        _log(traceback.format_exc())
        return False


CONFETTI_COLORS = (
    "#f44336", "#e91e63", "#9c27b0", "#673ab7", "#2196f3",
    "#03a9f4", "#4caf50", "#8bc34a", "#ffeb3b", "#ff9800", "#00bcd4",
)


class _ConfettiOverlay(QWidget):
    """Animated confetti layer for session-complete screens."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._particles = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start_burst(self, count=140):
        self._particles = []
        w = max(self.width(), 480)
        for _ in range(count):
            self._particles.append({
                "x": random.uniform(0, w),
                "y": random.uniform(-self.height() * 0.4, -8),
                "vx": random.uniform(-2.8, 2.8),
                "vy": random.uniform(2.5, 8.5),
                "w": random.uniform(6, 13),
                "h": random.uniform(4, 11),
                "rot": random.uniform(0, 360),
                "vr": random.uniform(-10, 10),
                "color": random.choice(CONFETTI_COLORS),
            })
        if not self._timer.isActive():
            self._timer.start(33)

    def _tick(self):
        gravity = 0.18
        h = self.height()
        alive = []
        for part in self._particles:
            part["vy"] += gravity
            part["x"] += part["vx"]
            part["y"] += part["vy"]
            part["rot"] += part["vr"]
            if part["y"] < h + 50:
                alive.append(part)
        self._particles = alive
        self.update()
        if not alive:
            self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for part in self._particles:
            painter.save()
            painter.translate(part["x"], part["y"])
            painter.rotate(part["rot"])
            painter.fillRect(
                QRectF(-part["w"] / 2, -part["h"] / 2, part["w"], part["h"]),
                QColor(part["color"]))
            painter.restore()


class SessionCompleteWindow(GatewayWindow):
    """Celebration screen shown when a session finishes."""

    def __init__(self, session_num):
        super().__init__("Session %d complete" % session_num)
        self._confetti = _ConfettiOverlay(self)

        heading = QLabel("Session %d completed!" % session_num)
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setStyleSheet(
            "color: #ffffff; font-size: 28px; font-weight: bold; padding: 0 12px;")
        heading.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        sub = QLabel("Thank you for taking part.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #f2f2f2; font-size: 16px; padding: 8px 12px;")

        continue_btn = QPushButton("Continue")
        continue_btn.setDefault(True)
        continue_btn.clicked.connect(lambda: self._finish(True))

        inner = QWidget()
        inner.setMinimumWidth(480)
        inner.setMaximumWidth(560)
        lay = QVBoxLayout(inner)
        lay.setSpacing(12)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.addWidget(heading)
        lay.addWidget(sub)
        lay.addSpacing(24)
        lay.addWidget(continue_btn, alignment=Qt.AlignCenter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.addStretch(1)
        outer.addWidget(inner, 0, Qt.AlignCenter)
        outer.addStretch(1)

        inner.adjustSize()
        self.adjustSize()
        self.setMinimumSize(560, max(360, inner.sizeHint().height() + 140))
        self._content = inner

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._confetti.setGeometry(self.rect())
        if self._content is not None:
            self._content.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self._confetti.setGeometry(self.rect())
        self._confetti.start_burst(160)
        self._confetti.lower()
        if self._content is not None:
            self._content.raise_()


def run_session_complete(session_num):
    """Show session-complete celebration; return True when the participant continues."""
    try:
        win = SessionCompleteWindow(session_num)
        suppress_krita_ui(win)
        return win.run_blocking() is True
    except Exception:
        _log(traceback.format_exc())
        return False
