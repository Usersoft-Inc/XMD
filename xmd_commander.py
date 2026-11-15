import datetime
import getpass
import keyword
import locale
import os
import shlex
import shutil
import socket
import stat
import sys

from PyQt6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontInfo, QFontMetrics, QIcon, QKeySequence, QPainter, QPalette, QPen, QPixmap,
    QShortcut, QSyntaxHighlighter, QTextCharFormat,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QScrollArea, QSplitter, QStackedWidget,
    QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

BG = "#101010"
BG_HEADER = "#1c1c1c"
BG_PATH = "#262626"
FG = "#d0d0d0"
FG_DIM = "#6a6a6a"
DIR_FG = "#6b9cf2"
SEL_BG = "#3a6fc4"
MARK_BG = "#3e6b3e"
HINT_BG = "#5fae5f"
ERR_BG = "#c0504d"
STATUS_BG = "#1b3263"
KEYBAR_BG = "#1f5fbf"
SCROLL = "#3a6fc4"
TITLE_BG = "#1f1f1f"
TITLE_H = 32
GRIP = 5

PATH_ROLE = Qt.ItemDataRole.UserRole + 1
DIR_ROLE = Qt.ItemDataRole.UserRole + 2
SIZE_ROLE = Qt.ItemDataRole.UserRole + 3
MARK_ROLE = Qt.ItemDataRole.UserRole + 4

MAX_PREVIEW = 5 * 1024 * 1024

COMMANDS = {
    "touch": ("PATH", "Create an empty file at PATH."),
    "mkdir": ("PATH", "Create a directory at PATH."),
    "rm": ("[PATH]", "Delete PATH or the selected files."),
    "mv": ("SRC DST", "Move or rename SRC to DST (or the highlighted item to DST)."),
    "cd": ("PATH", "Change the current directory to PATH."),
    "open": ("PATH", "Open PATH in the editor."),
    "w": ("", "Save the file open in the editor."),
    "q": ("", "Quit the application."),
}

STYLE = f"""
QMainWindow, QWidget {{ background: {BG}; color: {FG}; }}
QListWidget {{ background: {BG}; border: none; outline: none; }}
QPlainTextEdit {{ background: {BG}; color: #f8f8f2; border: none;
    selection-background-color: {SEL_BG}; selection-color: #ffffff; }}
QLineEdit {{ background: {BG}; color: #ffffff; border: none; padding: 0; }}
QSplitter::handle {{ background: #000000; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {SCROLL}; min-height: 20px; }}
QScrollBar:horizontal {{ background: transparent; height: 7px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {SCROLL}; min-width: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QMessageBox QLabel {{ color: {FG}; }}
QMessageBox QPushButton {{ background: #2a2a2a; color: {FG}; border: 1px solid #444;
    padding: 4px 14px; }}
QMessageBox QPushButton:focus {{ border: 1px solid {SEL_BG}; }}
"""


def human_size(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n}{unit}" if unit == "B" else f"{n:.0f}{unit}"
        n /= 1024


def owner_of(path):
    try:
        import pwd
        return pwd.getpwuid(os.stat(path).st_uid).pw_name
    except (ImportError, KeyError, OSError):
        return getpass.getuser()


def list_dir(path):
    try:
        entries = list(os.scandir(path))
    except OSError:
        return []
    result = []
    for e in entries:
        try:
            is_dir = e.is_dir()
        except OSError:
            is_dir = False
        if is_dir:
            try:
                size = str(len(os.listdir(e.path)))
            except OSError:
                size = "?"
        else:
            try:
                size = human_size(e.stat().st_size)
            except OSError:
                size = "?"
        result.append((e.name, e.path, is_dir, size))
    result.sort(key=lambda t: (not t[2], t[0].lower()))
    return result


class EntryDelegate(QStyledItemDelegate):
    def paint(self, p, opt, idx):
        p.save()
        r = opt.rect
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        marked = bool(idx.data(MARK_ROLE))
        is_dir = bool(idx.data(DIR_ROLE))
        if selected:
            p.fillRect(r, QColor(SEL_BG))
        elif marked:
            p.fillRect(r, QColor(MARK_BG))

        fm = opt.fontMetrics
        p.setFont(opt.font)
        size = idx.data(SIZE_ROLE) or ""
        num, unit = (size[:-1], size[-1]) if size and size[-1].isalpha() else (size, "")
        unit_w = fm.horizontalAdvance(unit)
        size_w = fm.horizontalAdvance(num) + unit_w

        name = idx.data(Qt.ItemDataRole.DisplayRole) + ("/" if is_dir else "")
        name_rect = r.adjusted(6, 0, -size_w - 16, 0)
        name = fm.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width())
        if selected:
            fg = QColor("#ffffff")
        elif is_dir:
            fg = QColor(DIR_FG)
        else:
            fg = QColor(FG)
        p.setPen(fg)
        p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        right = r.adjusted(0, 0, -8, 0)
        p.setPen(QColor(FG_DIM) if not selected else QColor("#c8d8f8"))
        p.drawText(right, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, unit)
        p.setPen(QColor("#a8a8a8") if not selected else QColor("#ffffff"))
        p.drawText(right.adjusted(0, 0, -unit_w, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, num)
        p.restore()

    def sizeHint(self, opt, idx):
        return QSize(opt.rect.width(), opt.fontMetrics.height() + 1)


class FileList(QListWidget):
    def __init__(self, focusable=True):
        super().__init__()
        self.setItemDelegate(EntryDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        if not focusable:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def fill(self, path, select_name=None):
        self.blockSignals(True)
        self.clear()
        row = 0
        for i, (name, full, is_dir, size) in enumerate(list_dir(path)):
            it = QListWidgetItem(name)
            it.setData(PATH_ROLE, full)
            it.setData(DIR_ROLE, is_dir)
            it.setData(SIZE_ROLE, size)
            it.setData(MARK_ROLE, False)
            self.addItem(it)
            if name == select_name:
                row = i
        if self.count():
            self.setCurrentRow(row)
            self.scrollToItem(self.currentItem(), QListWidget.ScrollHint.PositionAtCenter)
        self.blockSignals(False)

    def marked(self):
        return [self.item(i) for i in range(self.count()) if self.item(i).data(MARK_ROLE)]


class PythonHighlighter(QSyntaxHighlighter):
    KEYWORDS = set(keyword.kwlist) - {"True", "False", "None"}
    CONSTANTS = {"True", "False", "None", "self", "cls"}
    BUILTINS = {"print", "len", "range", "str", "int", "float", "dict", "list", "set",
                "tuple", "bool", "type", "object", "super", "isinstance", "open",
                "enumerate", "zip", "map", "filter", "sorted", "min", "max", "sum",
                "any", "all", "repr", "getattr", "setattr", "hasattr", "iter", "next",
                "Exception", "ValueError", "TypeError", "KeyError", "OSError"}
    STRING_PREFIXES = {"r", "b", "f", "u", "rb", "br", "fr", "rf"}

    def __init__(self, doc):
        super().__init__(doc)
        self.enabled = False

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        self.f_kw = fmt("#f92672")
        self.f_const = fmt("#ae81ff")
        self.f_builtin = fmt("#66d9ef")
        self.f_str = fmt("#e6db74")
        self.f_comment = fmt("#75715e", italic=True)
        self.f_num = fmt("#ae81ff")
        self.f_def = fmt("#a6e22e")
        self.f_deco = fmt("#a6e22e")

    def highlightBlock(self, text):
        if not self.enabled:
            return
        n = len(text)
        i = 0
        state = self.previousBlockState()
        if state in (1, 2):
            delim = '"""' if state == 1 else "'''"
            end = text.find(delim)
            if end == -1:
                self.setFormat(0, n, self.f_str)
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, end + 3, self.f_str)
            i = end + 3
        self.setCurrentBlockState(0)

        prev_word = ""
        while i < n:
            c = text[i]
            if c == "#":
                self.setFormat(i, n - i, self.f_comment)
                return
            if c in "\"'":
                i = self._string(text, i, i)
                if i < 0:
                    return
                continue
            if c == "@" and text[:i].strip() == "":
                j = i + 1
                while j < n and (text[j].isalnum() or text[j] in "_."):
                    j += 1
                self.setFormat(i, j - i, self.f_deco)
                i = j
                continue
            if c.isalpha() or c == "_":
                j = i
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                if word.lower() in self.STRING_PREFIXES and j < n and text[j] in "\"'":
                    i = self._string(text, j, i)
                    if i < 0:
                        return
                    continue
                if prev_word in ("def", "class"):
                    self.setFormat(i, j - i, self.f_def)
                elif word in self.KEYWORDS:
                    self.setFormat(i, j - i, self.f_kw)
                elif word in self.CONSTANTS:
                    self.setFormat(i, j - i, self.f_const)
                elif word in self.BUILTINS:
                    self.setFormat(i, j - i, self.f_builtin)
                prev_word = word
                i = j
                continue
            if c.isdigit():
                j = i
                while j < n and (text[j].isalnum() or text[j] in "._"):
                    j += 1
                self.setFormat(i, j - i, self.f_num)
                i = j
                continue
            if not c.isspace():
                prev_word = ""
            i += 1

    def _string(self, text, q, start):
        """Format a string literal starting at q; return next index or -1 if it spans lines."""
        n = len(text)
        quote = text[q]
        triple = text[q:q + 3] == quote * 3
        if triple:
            end = text.find(quote * 3, q + 3)
            if end == -1:
                self.setFormat(start, n - start, self.f_str)
                self.setCurrentBlockState(1 if quote == '"' else 2)
                return -1
            end += 3
        else:
            j = q + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            end = min(j + 1, n)
        self.setFormat(start, end - start, self.f_str)
        return end


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    escaped = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.lna = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_area)
        self.cursorPositionChanged.connect(self.lna.update)
        self.update_margin()

    def setFont(self, font):
        super().setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
        self.update_margin()

    def line_number_width(self):
        digits = max(3, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_margin(self, _=0):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def update_area(self, rect, dy):
        if dy:
            self.lna.scroll(0, dy)
        else:
            self.lna.update(0, rect.y(), self.lna.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.lna.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        p = QPainter(self.lna)
        p.fillRect(event.rect(), QColor(BG))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        cur = self.textCursor().blockNumber()
        h = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(QColor("#c8c8c8") if num == cur and self.hasFocus() else QColor("#5a5a5a"))
                p.drawText(0, top, self.lna.width() - 8, h, Qt.AlignmentFlag.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.lna.update()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.lna.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.escaped.emit()
            return
        if e.key() == Qt.Key.Key_Tab and not e.modifiers():
            self.insertPlainText("    ")
            return
        super().keyPressEvent(e)


def default_font():
    font = QFont()
    font.setFamilies(["JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"])
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(10)
    return font


def bar_label(bg, fg="#ffffff", font=None):
    lbl = QLabel()
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(f"background: {bg}; color: {fg}; padding: 0 6px;")
    lbl.setFixedHeight(QFontMetrics(font or QApplication.font()).height() + 4)
    lbl.setMinimumWidth(1)
    return lbl


ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commander.ico")
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def draw_icon(size):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(SEL_BG))
    m = size / 32
    p.drawRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), size * 0.19, size * 0.19)
    f = QFont("Consolas")
    f.setBold(True)
    f.setPixelSize(max(8, round(size * 0.5)))
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, ">_")
    p.end()
    return pm


def make_icon():
    if os.path.isfile(ICON_FILE):
        return QIcon(ICON_FILE)
    icon = QIcon()
    for s in ICON_SIZES:
        icon.addPixmap(draw_icon(s))
    return icon


def save_icon_files():
    """Write commander.ico (PNG-compressed entries) and commander.png next to the script."""
    import struct
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    blobs = []
    for s in ICON_SIZES:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        draw_icon(s).save(buf, "PNG")
        blobs.append((s, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    for s, png in blobs:
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    with open(ICON_FILE, "wb") as f:
        f.write(header + entries + b"".join(png for _, png in blobs))
    draw_icon(256).save(os.path.splitext(ICON_FILE)[0] + ".png", "PNG")


class CaptionButton(QAbstractButton):
    def __init__(self, kind, parent):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(46, TITLE_H)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        hover, down = self.underMouse(), self.isDown()
        if self.kind == "close" and (hover or down):
            p.fillRect(self.rect(), QColor("#f1707a" if down else "#e81123"))
        elif hover or down:
            p.fillRect(self.rect(), QColor("#3d3d3d" if down else "#2d2d2d"))
        if hover or down:
            color = "#ffffff"
        else:
            color = "#d8d8d8" if self.window().isActiveWindow() else "#6f6f6f"
        pen = QPen(QColor(color))
        pen.setCosmetic(True)
        p.setPen(pen)
        cx, cy = self.width() // 2, self.height() // 2
        if self.kind == "min":
            p.drawLine(cx - 5, cy, cx + 5, cy)
        elif self.kind == "max":
            if self.window().isMaximized():
                p.drawRect(cx - 5, cy - 3, 8, 8)
                p.drawLine(cx - 3, cy - 5, cx + 5, cy - 5)
                p.drawLine(cx + 5, cy - 5, cx + 5, cy + 3)
            else:
                p.drawRect(cx - 5, cy - 5, 10, 10)
        else:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            p.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)


class TitleBar(QWidget):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self._press = None
        self.setFixedHeight(TITLE_H)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {TITLE_BG};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(8)
        self.icon = QLabel()
        self.icon.setPixmap(win.windowIcon().pixmap(QSize(16, 16), self.devicePixelRatioF()))
        self.title = QLabel(win.windowTitle())
        self.title.setMinimumWidth(1)
        tf = QFont("Segoe UI")
        tf.setPointSize(9)
        self.title.setFont(tf)
        win.windowTitleChanged.connect(self.title.setText)
        lay.addWidget(self.icon)
        lay.addWidget(self.title, 1)
        self.btn_min = CaptionButton("min", self)
        self.btn_max = CaptionButton("max", self)
        self.btn_close = CaptionButton("close", self)
        self.btn_min.clicked.connect(win.showMinimized)
        self.btn_max.clicked.connect(win.toggle_maximized)
        self.btn_close.clicked.connect(win.close)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)
        self.update_state()

    def update_state(self):
        color = "#e8e8e8" if self.win.isActiveWindow() else "#7a7a7a"
        self.title.setStyleSheet(f"background: transparent; color: {color};")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._press is not None and \
                (e.globalPosition().toPoint() - self._press).manhattanLength() >= QApplication.startDragDistance():
            self._press = None
            self.win.windowHandle().startSystemMove()

    def mouseReleaseEvent(self, e):
        self._press = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = None
            self.win.toggle_maximized()


class ResizeGrip(QWidget):
    def __init__(self, win, edges, cursor):
        super().__init__(win)
        self.edges = edges
        self.setCursor(cursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemResize(self.edges)


class WindowFrame(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#4a4a4a" if self.window().isActiveWindow() else "#2a2a2a"))


class HelpDialog(QDialog):
    def __init__(self, parent, sections):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("helpDialog")
        self.setStyleSheet(f"QDialog#helpDialog {{ background: {BG}; border: 1px solid {SEL_BG}; }}")
        font = parent.font()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)
        self.header = bar_label(KEYBAR_BG, font=font)
        self.header.setText("<b>Help</b>")
        self.header.setCursor(Qt.CursorShape.SizeAllCursor)
        self.header.installEventFilter(self)
        lay.addWidget(self.header)
        body = QLabel(self.html(sections))
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setContentsMargins(10, 6, 10, 6)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        footer = bar_label(BG_HEADER, FG_DIM, font)
        footer.setText("Esc · Enter · ? &nbsp;close")
        lay.addWidget(footer)

        host = parent.window()
        width = min(QFontMetrics(font).horizontalAdvance("0") * 78, host.width() - 40)
        height = (body.heightForWidth(width - 2) + self.header.height() + footer.height() + 4)
        height = min(height, host.height() - 40)
        self.resize(width, height)
        center = host.mapToGlobal(host.rect().center())
        self.move(center - QPoint(width // 2, height // 2))

    @staticmethod
    def html(sections):
        rows = []
        for title, items in sections:
            rows.append(f'<tr><td colspan="2" style="color:{HINT_BG};font-weight:bold;padding-top:6px">'
                        f'{CommanderPanel.esc(title)}</td></tr>')
            for key, desc in items:
                rows.append(f'<tr><td style="color:#ffffff;white-space:nowrap;padding-right:16px">{key}</td>'
                            f'<td style="color:{FG}">{CommanderPanel.esc(desc).replace("&nbsp;", " ")}</td></tr>')
        return f'<table cellspacing="0" cellpadding="1">{"".join(rows)}</table>'

    def eventFilter(self, obj, e):
        if obj is self.header and e.type() == QEvent.Type.MouseButtonPress:
            self.windowHandle().startSystemMove()
            return True
        return super().eventFilter(obj, e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Q) or e.text() == "?":
            self.accept()
        else:
            super().keyPressEvent(e)


class CommanderPanel(QWidget):
    cwd_changed = pyqtSignal(str)
    exit_requested = pyqtSignal()

    def __init__(self, start, embedded=False, font=None, parent=None):
        super().__init__(parent)
        self.embedded = embedded
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        font = font or default_font()
        # Host apps may not propagate setFont() to children, so pin the font via the stylesheet too.
        family = QFontInfo(font).family()
        self.setStyleSheet(STYLE + f'\nQWidget {{ font-family: "{family}"; font-size: {font.pointSize()}pt; }}')
        self.setFont(font)
        self.cwd = os.path.abspath(start)
        self.shell = None
        self.commands = COMMANDS
        self.open_file = None
        self.open_encoding = "utf-8"
        self.open_newline = "\n"
        self.prev_row = -1
        self._sized = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.host_label = bar_label(BG_HEADER, "#a0a0a0", self.font())
        self.host_label.setText(f"{getpass.getuser()}@{socket.gethostname()}")
        self.parent_list = FileList(focusable=False)
        self.parent_list.itemClicked.connect(lambda it: self.enter_dir(it.data(PATH_ROLE))
                                             if it.data(DIR_ROLE) else None)
        self.cur_list = FileList()
        self.cur_list.currentRowChanged.connect(self.on_row_changed)
        self.cur_list.itemDoubleClicked.connect(lambda _: self.activate())

        inner = QSplitter(Qt.Orientation.Horizontal)
        inner.setHandleWidth(1)
        inner.addWidget(self.parent_list)
        inner.addWidget(self.cur_list)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        lv.addWidget(self.host_label)
        lv.addWidget(inner)

        self.path_label = bar_label(BG_PATH, "#8a8a8a", self.font())
        self.editor = CodeEditor()
        self.editor.escaped.connect(lambda: self.cur_list.setFocus())
        self.editor.document().modificationChanged.connect(lambda _: self.update_path_label())
        self.highlighter = PythonHighlighter(self.editor.document())
        self.dir_preview = FileList(focusable=False)
        self.dir_preview.itemClicked.connect(lambda it: self.enter_dir(it.data(PATH_ROLE))
                                             if it.data(DIR_ROLE) else None)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.editor)
        self.stack.addWidget(self.dir_preview)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self.path_label)
        rv.addWidget(self.stack)

        outer = QSplitter(Qt.Orientation.Horizontal)
        outer.setHandleWidth(1)
        outer.addWidget(left)
        outer.addWidget(right)
        self.inner, self.outer = inner, outer
        root.addWidget(outer, 1)

        self.hint = bar_label(HINT_BG, "#0b1a0b", self.font())
        self.hint.hide()
        root.addWidget(self.hint)

        cmd_row = QWidget()
        cmd_row.setFixedHeight(self.hint.height())
        ch = QHBoxLayout(cmd_row)
        ch.setContentsMargins(6, 0, 0, 0)
        ch.setSpacing(6)
        prompt = QLabel(">>>")
        prompt.setStyleSheet(f"color: {HINT_BG}; font-weight: bold;")
        self.cmd = QLineEdit()
        self.cmd.textChanged.connect(self.update_hint)
        self.cmd.returnPressed.connect(self.run_command)
        self.sel_label = bar_label("#333333", "#e0e0e0", self.font())
        self.sel_label.hide()
        ch.addWidget(prompt)
        ch.addWidget(self.cmd, 1)
        ch.addWidget(self.sel_label)
        root.addWidget(cmd_row)

        status = QWidget()
        status.setStyleSheet(f"background: {STATUS_BG};")
        sh = QHBoxLayout(status)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(0)
        self.status_left = bar_label(STATUS_BG, "#9fb4dc", self.font())
        self.status_right = bar_label(STATUS_BG, "#9fb4dc", self.font())
        sh.addWidget(self.status_left, 1)
        sh.addWidget(self.status_right)
        root.addWidget(status)

        keys = [("?", "Help"), (":", "Command line"), ("Tab", "Editor"),
                ("ctrl+s", "Save"), ("ctrl+q", "Back" if embedded else "Quit"),
                ("ESC", "Back" if embedded else "Cancel")]
        keybar = bar_label(KEYBAR_BG, font=self.font())
        keybar.setStyleSheet(f"background: {KEYBAR_BG}; color: #dfe8ff; padding: 0;")
        keybar.setText("".join(
            f'<span style="background:#0d2f6e;color:#ffffff;font-weight:bold">&nbsp;{k}&nbsp;</span>'
            f'<span>&nbsp;{label}&nbsp;</span>' for k, label in keys))
        root.addWidget(keybar)

        self.flash_timer = QTimer(self, singleShot=True, timeout=self.end_flash)

        for seq, slot in (("Ctrl+Q", self.request_exit), ("Ctrl+S", self.save_file)):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
        self.cur_list.installEventFilter(self)
        self.cmd.installEventFilter(self)

        self.editor.setFont(self.font())
        self.refresh()

    def focus_list(self):
        self.cur_list.setFocus()

    def set_shell(self, runner, commands):
        """runner(line) -> (lines, cleared); each line is a list of (text, style) segments."""
        self.shell = runner
        self.commands = commands

    def navigate(self, path):
        path = os.path.abspath(path)
        if path == self.cwd:
            self.refresh()
        elif os.path.isdir(path) and self.maybe_save():
            self.cwd = path
            self.cur_list.clear()
            self.refresh()

    def request_exit(self):
        if self.maybe_save():
            self.exit_requested.emit()

    def keyPressEvent(self, e):
        # Stop unhandled keys from reaching a host window (e.g. the xmd console input).
        e.accept()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._sized and self.width() > 100:
            self._sized = True
            w = self.width()
            self.outer.setSizes([int(w * 0.49), w - int(w * 0.49)])
            self.inner.setSizes([int(w * 0.20), int(w * 0.29)])

    # ---------- navigation ----------
    def refresh(self, select=None):
        if select is None and self.cur_list.currentItem():
            select = self.cur_list.currentItem().text()
        self.cur_list.fill(self.cwd, select)
        self.cwd_changed.emit(self.cwd)
        parent = os.path.dirname(self.cwd)
        if parent and parent != self.cwd:
            self.parent_list.fill(parent, os.path.basename(self.cwd))
        else:
            self.parent_list.clear()
        self.prev_row = -1
        self.on_row_changed(self.cur_list.currentRow())
        self.update_selected_count()

    def enter_dir(self, path):
        if not os.path.isdir(path) or not self.maybe_save():
            return
        self.cwd = os.path.abspath(path)
        self.cur_list.clear()
        self.refresh()

    def go_parent(self):
        parent = os.path.dirname(self.cwd)
        if not parent or parent == self.cwd or not self.maybe_save():
            return
        old = os.path.basename(self.cwd)
        self.cwd = parent
        self.refresh(select=old)

    def activate(self):
        it = self.cur_list.currentItem()
        if not it:
            return
        if it.data(DIR_ROLE):
            self.enter_dir(it.data(PATH_ROLE))
        elif self.open_file == it.data(PATH_ROLE) and not self.editor.isReadOnly():
            self.editor.setFocus()

    def on_row_changed(self, row):
        if row == self.prev_row and row != -1:
            return
        if not self.maybe_save():
            self.cur_list.blockSignals(True)
            self.cur_list.setCurrentRow(self.prev_row)
            self.cur_list.blockSignals(False)
            return
        self.prev_row = row
        it = self.cur_list.currentItem()
        if it is None:
            self.show_text(None, "")
        elif it.data(DIR_ROLE):
            self.open_file = None
            self.dir_preview.fill(it.data(PATH_ROLE))
            self.stack.setCurrentWidget(self.dir_preview)
        else:
            self.load_file(it.data(PATH_ROLE))
        self.update_path_label()
        self.update_status()

    # ---------- editor ----------
    def show_text(self, path, text, read_only=True):
        self.open_file = path
        self.highlighter.enabled = bool(path) and path.lower().endswith((".py", ".pyw", ".pyi"))
        self.editor.setPlainText(text)
        self.editor.setReadOnly(read_only)
        self.editor.document().setModified(False)
        self.stack.setCurrentWidget(self.editor)

    def load_file(self, path):
        try:
            size = os.path.getsize(path)
            if size > MAX_PREVIEW:
                return self.show_text(None, f"File is too large to preview ({human_size(size)}).")
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            return self.show_text(None, f"Cannot read file: {e}")
        if b"\0" in raw[:8192]:
            return self.show_text(None, "Binary file.")
        for enc in ("utf-8", locale.getpreferredencoding(False), "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        self.open_encoding = enc
        self.open_newline = "\r\n" if b"\r\n" in raw else "\n"
        self.show_text(path, text.replace("\r\n", "\n"), read_only=False)

    def save_file(self):
        if not self.open_file or self.editor.isReadOnly():
            return False
        data = self.editor.toPlainText().replace("\n", self.open_newline)
        try:
            with open(self.open_file, "wb") as f:
                f.write(data.encode(self.open_encoding, errors="replace"))
        except OSError as e:
            self.flash(f"Save failed: {e}", error=True)
            return False
        self.editor.document().setModified(False)
        self.flash(f"Saved {os.path.basename(self.open_file)}")
        self.refresh_sizes()
        return True

    def maybe_save(self):
        if not self.open_file or not self.editor.document().isModified():
            return True
        btn = QMessageBox.question(
            self, "Unsaved changes", f"Save changes to {os.path.basename(self.open_file)}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if btn == QMessageBox.StandardButton.Save:
            return self.save_file()
        if btn == QMessageBox.StandardButton.Discard:
            self.editor.document().setModified(False)
            return True
        return False

    def refresh_sizes(self):
        it = self.cur_list.currentItem()
        if it and not it.data(DIR_ROLE):
            try:
                it.setData(SIZE_ROLE, human_size(os.path.getsize(it.data(PATH_ROLE))))
            except OSError:
                pass
        self.update_status()

    # ---------- bars ----------
    def update_path_label(self):
        it = self.cur_list.currentItem()
        path = it.data(PATH_ROLE) if it else self.cwd
        head, tail = os.path.split(path)
        head = head.rstrip("\\/") + os.sep
        mod = ""
        if self.open_file and self.editor.document().isModified():
            mod = '&nbsp;<span style="color:#e6db74">[+]</span>'
        self.path_label.setText(f"{self.esc(head)}<b style='color:#ffffff'>{self.esc(tail)}</b>{mod}")

    def update_status(self):
        it = self.cur_list.currentItem()
        sep = '<span style="color:#4a6aa8">&nbsp;╲&nbsp;</span>'
        try:
            du = shutil.disk_usage(self.cwd)
            self.status_right.setText(f"{human_size(du.free)} free of {human_size(du.total)}")
        except OSError:
            self.status_right.setText("")
        if not it:
            self.status_left.setText("")
            return
        path = it.data(PATH_ROLE)
        try:
            st = os.stat(path)
        except OSError:
            self.status_left.setText("")
            return
        colors = {"r": "#e5c07b", "w": "#e06c75", "x": "#98c379", "d": DIR_FG, "-": "#5a6f99"}
        perms = "".join(f'<span style="color:{colors.get(ch, "#9fb4dc")}">{ch}</span>'
                        for ch in stat.filemode(st.st_mode))
        dt = datetime.datetime.fromtimestamp(st.st_mtime)
        size = it.data(SIZE_ROLE) if not it.data(DIR_ROLE) else human_size(st.st_size)
        date = f"{dt.day} {dt:%b %y %H:%M}"
        self.status_left.setText(sep.join([perms, size, date, self.esc(owner_of(path))]) + sep)

    def update_selected_count(self):
        n = len(self.cur_list.marked())
        self.sel_label.setVisible(n > 0)
        self.sel_label.setText(f"{n} file{'s' if n != 1 else ''} selected")

    def update_hint(self):
        if self.flash_timer.isActive():
            return
        self.hint.setStyleSheet(f"background: {HINT_BG}; color: #0b1a0b; padding: 0 6px;")
        word = self.cmd.text().strip().split(" ")[0] if self.cmd.text().strip() else ""
        matches = [c for c in self.commands
                   if any(n.startswith(word.lower()) for n in c.split("|"))] if word else []
        if matches:
            name = matches[0]
            args, desc = self.commands[name]
            label = f"{name.replace('|', ' | ')} {args}".strip()
            self.hint.setText(f"<b>{self.esc(label)}</b>&nbsp;&nbsp;&nbsp;{self.esc(desc)}")
        elif word:
            self.hint.setText(f"Unknown command: <b>{self.esc(word)}</b>")
        else:
            self.hint.setText("Commands:&nbsp;&nbsp;" + "&nbsp;·&nbsp;".join(
                f"<b>{self.esc(c.replace('|', ' | '))}</b>" for c in self.commands))
        self.hint.show()

    def flash(self, text, error=False):
        bg = ERR_BG if error else HINT_BG
        fg = "#ffffff" if error else "#0b1a0b"
        self.hint.setStyleSheet(f"background: {bg}; color: {fg}; padding: 0 6px;")
        self.hint.setText(self.esc(text))
        self.hint.show()
        self.flash_timer.start(3000)

    def end_flash(self):
        if self.cmd.hasFocus():
            self.update_hint()
        else:
            self.hint.hide()

    @staticmethod
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")

    # ---------- commands ----------
    def resolve(self, p):
        return os.path.abspath(os.path.join(self.cwd, os.path.expanduser(p)))

    def run_command(self):
        line = self.cmd.text().strip()
        self.cmd.clear()
        self.cur_list.setFocus()
        if not line:
            return
        if self.shell:
            return self.run_shell(line)
        try:
            parts = shlex.split(line, posix=os.name != "nt")
            parts = [p.strip('"').strip("'") for p in parts]
        except ValueError as e:
            return self.flash(str(e), error=True)
        name, args = parts[0], parts[1:]
        try:
            self.execute(name, args)
        except OSError as e:
            self.flash(str(e), error=True)

    def run_shell(self, line):
        if not self.maybe_save():
            return
        lines, cleared = self.shell(line)
        if cleared and not lines:
            self.prev_row = -1
            self.on_row_changed(self.cur_list.currentRow())
            return
        if not lines:
            return
        error = any(style == "error" for row in lines for _, style in row)
        text = ["".join(str(t) for t, _ in row) for row in lines]
        while text and not text[-1].strip():
            text.pop()
        if len(text) == 1:
            return self.flash(text[0], error=error)
        self.show_text(None, "\n".join(text))
        self.path_label.setText(f"<b style='color:#ffffff'>&gt;&gt;&gt;&nbsp;{self.esc(line)}</b>")
    def execute(self, name, args):
        cur = self.cur_list.currentItem()
        if name == "touch" and args:
            for a in args:
                path = self.resolve(a)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "a").close()
            self.refresh(select=os.path.basename(self.resolve(args[0])))
            self.flash(f"Created {', '.join(args)}")
        elif name == "mkdir" and args:
            for a in args:
                os.makedirs(self.resolve(a), exist_ok=True)
            self.refresh(select=os.path.basename(self.resolve(args[0])))
            self.flash(f"Created directory {', '.join(args)}")
        elif name == "rm":
            targets = [self.resolve(a) for a in args] or \
                [it.data(PATH_ROLE) for it in self.cur_list.marked()] or \
                ([cur.data(PATH_ROLE)] if cur else [])
            if not targets:
                return
            names = "\n".join(os.path.basename(t) for t in targets[:15])
            more = f"\n... and {len(targets) - 15} more" if len(targets) > 15 else ""
            if QMessageBox.question(self, "Delete", f"Delete {len(targets)} item(s)?\n\n{names}{more}") \
                    != QMessageBox.StandardButton.Yes:
                return
            for t in targets:
                if self.open_file and os.path.abspath(self.open_file) == t:
                    self.editor.document().setModified(False)
                if os.path.isdir(t) and not os.path.islink(t):
                    shutil.rmtree(t)
                else:
                    os.remove(t)
            row = self.cur_list.currentRow()
            self.refresh()
            self.cur_list.setCurrentRow(min(row, self.cur_list.count() - 1))
            self.flash(f"Deleted {len(targets)} item(s)")
        elif name == "mv" and args:
            if len(args) == 1:
                if not cur:
                    return
                src, dst = cur.data(PATH_ROLE), self.resolve(args[0])
            else:
                src, dst = self.resolve(args[0]), self.resolve(args[1])
            if self.open_file and os.path.abspath(self.open_file) == src and not self.maybe_save():
                return
            shutil.move(src, dst)
            target = dst if os.path.dirname(dst) == self.cwd else None
            self.refresh(select=os.path.basename(target) if target else None)
            self.flash(f"Moved {os.path.basename(src)} -> {dst}")
        elif name == "cd":
            path = self.resolve(args[0]) if args else os.path.expanduser("~")
            if not os.path.isdir(path):
                return self.flash(f"Not a directory: {path}", error=True)
            self.enter_dir(path)
        elif name == "open" and args:
            path = self.resolve(args[0])
            if not os.path.isfile(path):
                return self.flash(f"No such file: {path}", error=True)
            if not self.maybe_save():
                return
            self.cwd = os.path.dirname(path)
            self.refresh(select=os.path.basename(path))
            if not self.editor.isReadOnly():
                self.editor.setFocus()
        elif name in ("w", "save"):
            if not self.save_file():
                self.flash("No editable file is open.", error=True)
        elif name in ("q", "quit"):
            self.request_exit()
        elif name in COMMANDS:
            self.flash(f"Usage: {name} {COMMANDS[name][0]}", error=True)
        else:
            self.flash(f"Unknown command: {name}", error=True)

    def show_help(self):
        nav = [("Up/Down, j/k", "move"), ("Right/Enter, l", "open directory / edit file"),
               ("Left/Backspace, h", "parent directory"), ("Space", "select / unselect"),
               ("Tab", "focus editor (Esc to return)"), (":", "command line"), ("Ctrl+S", "save file")]
        nav += ([("Ctrl+Q, q", "back to the console"), ("Esc", "clear selection / back to the console")]
                if self.embedded else [("Ctrl+Q", "quit"), ("Esc", "cancel / clear selection")])
        nav = [(self.esc(k), d) for k, d in nav]
        cmds = [(f"<b>{self.esc(name.replace('|', ' | '))}</b>"
                 + (f"&nbsp;<span style='color:{FG_DIM}'>{self.esc(args)}</span>" if args else ""), desc)
                for name, (args, desc) in self.commands.items()]
        HelpDialog(self, [("Navigation", nav), ("Commands", cmds)]).exec()
        self.cur_list.setFocus()

    # ---------- events ----------
    def eventFilter(self, obj, e):
        if obj is self.cmd:
            if e.type() == QEvent.Type.FocusIn:
                self.update_hint()
            elif e.type() == QEvent.Type.FocusOut and not self.flash_timer.isActive():
                self.hint.hide()
            elif e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key.Key_Escape:
                self.cmd.clear()
                self.cur_list.setFocus()
                return True
        elif obj is self.cur_list and e.type() == QEvent.Type.KeyPress:
            key, txt = e.key(), e.text()
            if key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter) or txt == "l":
                self.activate()
                return True
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace) or txt == "h":
                self.go_parent()
                return True
            if txt == "j":
                self.cur_list.setCurrentRow(min(self.cur_list.currentRow() + 1, self.cur_list.count() - 1))
                return True
            if txt == "k":
                self.cur_list.setCurrentRow(max(self.cur_list.currentRow() - 1, 0))
                return True
            if key == Qt.Key.Key_Space:
                it = self.cur_list.currentItem()
                if it:
                    it.setData(MARK_ROLE, not it.data(MARK_ROLE))
                    self.cur_list.setCurrentRow(min(self.cur_list.currentRow() + 1, self.cur_list.count() - 1))
                    self.update_selected_count()
                return True
            if key == Qt.Key.Key_Tab:
                if self.stack.currentWidget() is self.editor and not self.editor.isReadOnly():
                    self.editor.setFocus()
                return True
            if key == Qt.Key.Key_Escape:
                marked = self.cur_list.marked()
                for it in marked:
                    it.setData(MARK_ROLE, False)
                self.update_selected_count()
                if not marked and self.embedded:
                    self.request_exit()
                return True
            if txt == ":":
                self.cmd.setFocus()
                return True
            if txt == "?":
                self.show_help()
                return True
        return super().eventFilter(obj, e)


class Commander(QMainWindow):
    def __init__(self, start):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(make_icon())
        self.setWindowTitle("Commander")
        self.setMinimumSize(640, 400)
        E = Qt.Edge
        C = Qt.CursorShape
        self.grips = {
            "t": ResizeGrip(self, E.TopEdge, C.SizeVerCursor),
            "b": ResizeGrip(self, E.BottomEdge, C.SizeVerCursor),
            "l": ResizeGrip(self, E.LeftEdge, C.SizeHorCursor),
            "r": ResizeGrip(self, E.RightEdge, C.SizeHorCursor),
            "tl": ResizeGrip(self, E.TopEdge | E.LeftEdge, C.SizeFDiagCursor),
            "br": ResizeGrip(self, E.BottomEdge | E.RightEdge, C.SizeFDiagCursor),
            "tr": ResizeGrip(self, E.TopEdge | E.RightEdge, C.SizeBDiagCursor),
            "bl": ResizeGrip(self, E.BottomEdge | E.LeftEdge, C.SizeBDiagCursor),
        }
        self.resize(1200, 760)

        self.frame = WindowFrame()
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(1, 1, 1, 1)
        self.frame_layout.setSpacing(0)
        self.titlebar = TitleBar(self)
        self.frame_layout.addWidget(self.titlebar)
        self.panel = CommanderPanel(start)
        self.panel.cwd_changed.connect(lambda p: self.setWindowTitle(f"{p} - Commander"))
        self.panel.exit_requested.connect(self.close)
        self.setWindowTitle(f"{self.panel.cwd} - Commander")
        self.frame_layout.addWidget(self.panel, 1)
        self.setCentralWidget(self.frame)
        self.panel.focus_list()

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_placed", False):
            self._placed = True
            self.move(self.screen().availableGeometry().center() - self.rect().center())
            if sys.platform == "win32":
                # Frameless windows lack WS_MINIMIZEBOX, so the taskbar button can't minimize them.
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = int(self.winId())
                style = user32.GetWindowLongW(hwnd, -16)
                user32.SetWindowLongW(hwnd, -16, style | 0x00020000 | 0x00010000)
        self.place_grips()

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def place_grips(self):
        w, h, g, c = self.width(), self.height(), GRIP, GRIP * 2
        geo = {"t": (c, 0, w - 2 * c, g), "b": (c, h - g, w - 2 * c, g),
               "l": (0, c, g, h - 2 * c), "r": (w - g, c, g, h - 2 * c),
               "tl": (0, 0, c, c), "tr": (w - c, 0, c, c),
               "bl": (0, h - c, c, c), "br": (w - c, h - c, c, c)}
        visible = not (self.isMaximized() or self.isFullScreen())
        for key, grip in self.grips.items():
            grip.setGeometry(*geo[key])
            grip.setVisible(visible)
            grip.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.place_grips()

    def changeEvent(self, e):
        if hasattr(self, "titlebar"):
            if e.type() == QEvent.Type.WindowStateChange:
                m = 0 if self.isMaximized() or self.isFullScreen() else 1
                self.frame_layout.setContentsMargins(m, m, m, m)
                self.place_grips()
                self.titlebar.update_state()
            elif e.type() == QEvent.Type.ActivationChange:
                self.frame.update()
                self.titlebar.update_state()
        super().changeEvent(e)

    def closeEvent(self, e):
        if self.panel.maybe_save():
            e.accept()
        else:
            e.ignore()


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XMD.Commander")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = default_font()
    app.setFont(font)
    pal = app.palette()
    for role, color in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, BG),
                        (QPalette.ColorRole.Text, FG), (QPalette.ColorRole.WindowText, FG),
                        (QPalette.ColorRole.Button, "#2a2a2a"), (QPalette.ColorRole.ButtonText, FG),
                        (QPalette.ColorRole.Highlight, SEL_BG)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(STYLE)

    if "--make-icon" in sys.argv:
        save_icon_files()
        print(f"Saved {ICON_FILE}")
        return

    start = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    win = Commander(start)
    win.show()
    win.raise_()
    win.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
