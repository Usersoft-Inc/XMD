# -*- coding: utf-8 -*-
"""XMD incremental compatibility layer over the recovered application core."""
import fnmatch
import importlib.util
import json
import marshal
import os
import shutil
import stat
import tempfile
import subprocess
import sys
import time
from pathlib import Path

from xmd_commander import CommanderPanel
import xmd_diagnostics

# Keep the GUI dependencies visible to PyInstaller; the recovered module is loaded from marshal.
import PyQt6.QtCore  # noqa: F401
import PyQt6.QtGui  # noqa: F401
import PyQt6.QtWidgets  # noqa: F401
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QIcon, QTextCharFormat
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QComboBox, QSlider, QCheckBox, QLineEdit, QScrollArea,
                             QInputDialog, QMessageBox, QDialog, QFrame, QGraphicsDropShadowEffect)

FROZEN = getattr(sys, "frozen", False)
# In a --onefile build __file__ lives in a temporary _MEI folder that is deleted on exit.
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
APP_VERSION = "2.0"
xmd_diagnostics.configure(APP_DIR)
DEBUG_MODE = True
_payload_candidates = (os.path.join(BUNDLE_DIR, "main.recovered.pyc"),
                       os.path.join(APP_DIR, "main.recovered.pyc"),
                       os.path.join(APP_DIR, "cache", "main.recovered.pyc"))
PAYLOAD = next((c for c in _payload_candidates if os.path.isfile(c)), _payload_candidates[0])
_spec = importlib.util.spec_from_loader("_xsh_recovered", loader=None)
_xsh = importlib.util.module_from_spec(_spec)
_xsh.__file__ = os.path.join(APP_DIR, "main.py")
sys.modules[_spec.name] = _xsh
with open(PAYLOAD, "rb") as _f:
    exec(marshal.loads(_f.read()), _xsh.__dict__)
_xsh.APP_VERSION = APP_VERSION
_xsh.XSHCLI_VERSION = "v2.0"
_xsh.PROMPT_BRANCH = r"xmd\database"
APP_NAME = "XMD"
_xsh.APP_NAME = APP_NAME
_xsh.HOME_LABEL = "xmd"
_xsh.USER_NAME = "xmd"


def _set_app_id():
    if os.name != "nt": return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XSystem.XMD")
    except Exception:
        pass


_xsh._set_app_id = _set_app_id


def _resolve(core, value):
    value = os.path.expandvars(os.path.expanduser(value))
    return os.path.normpath(os.path.join(core.cwd, value))


def _details(path, out):
    st = os.stat(path)
    rows = (("Name", os.path.basename(path) or path), ("Path", os.path.abspath(path)),
            ("Type", "Directory" if os.path.isdir(path) else "File"), ("Size", str(st.st_size)),
            ("Modified", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))),
            ("Created", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_ctime))))
    for key, value in rows: out.write([(f"{key}: {value}", "plain")])


def _history(path, out):
    st = os.stat(path)
    for label, stamp in (("Created", st.st_ctime), ("Modified", st.st_mtime), ("Accessed", st.st_atime)):
        out.write([(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))}  {label}", "plain")])


def _launch(core, path, out):
    if os.path.isdir(path):
        core.cwd = core.current = path
    else:
        try:
            if os.name == "nt": os.startfile(path)
            else: subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc: out.write([(f"xsh: {exc}", "error")])


def _cmd_list(self, args, out):
    detailed = absolute = False
    action = None
    element = None
    target_parts = []
    i = 0
    while i < len(args):
        item = args[i]; low = item.lower()
        if low == "-l": detailed = True
        elif low == "-a": absolute = True
        elif low in ("-v", "-boot", "-b", "-del", "-delete", "-set") or low.startswith("-set:"):
            if action is not None:
                out.write([("xsh: only one action attribute can be used at a time", "error")]); return
            action = "history" if low == "-v" else ("boot" if low in ("-boot", "-b") else
                     "delete" if low in ("-del", "-delete") else "details")
            if low.startswith("-set:"):
                element = item.split(":", 1)[1].strip("\"'")
            if not element and i + 1 < len(args):
                i += 1; element = args[i].strip("\"'")
            while element and i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1; element += " " + args[i]
        elif item.startswith("-"):
            out.write([(f"xsh: unknown attribute: {item}", "error")]); return
        else:
            target_parts.append(item)
        i += 1
    if absolute and action:
        out.write([("xsh: -a cannot be combined with -set, -boot, -del, or -v", "error")]); return
    if action:
        if not element:
            out.write([(f"xsh: {action} requires an element name", "error")]); return
        path = _resolve(self, element)
        if not os.path.exists(path):
            out.write([(f"xsh: element not found: {element}", "error")]); return
        try:
            if action == "delete":
                shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
            elif action == "boot": _launch(self, path, out)
            elif action == "history": _history(path, out)
            else: _details(path, out)
        except OSError as exc: out.write([(f"xsh: {exc}", "error")])
        return
    target = " ".join(target_parts) if target_parts else None
    path = _resolve(self, target) if target else self.cwd
    if not os.path.isdir(path):
        out.write([(f"xsh: directory not found: {path}", "error")]); return
    entries = self.scan(path)
    if absolute:
        for entry in entries:
            out.write([(os.path.abspath(os.path.join(path, entry.name.rstrip("/\\"))), "plain")])
    else:
        rows = _xsh.format_long(entries) if detailed else _xsh.format_short(entries, getattr(out, "columns", 80))
        for row in rows: out.write(row)
        out.write([])


def _swap_file_objects_keep_path_data(a,b):
    a=os.path.abspath(a); b=os.path.abspath(b)
    if a==b: return
    if not os.path.isfile(a) or not os.path.isfile(b):
        raise OSError("-rplc requires two existing files")
    if os.stat(a).st_dev != os.stat(b).st_dev:
        raise OSError("-rplc can only swap files on the same drive")

    def reserve(directory):
        fd,path=tempfile.mkstemp(prefix=".xsh-rplc-",dir=directory)
        os.close(fd)
        return path

    dir_a=os.path.dirname(a); dir_b=os.path.dirname(b)
    backup_a=reserve(dir_a); backup_b=reserve(dir_b)
    swap_a=reserve(dir_a); swap_b=reserve(dir_b)
    try:
        shutil.copy2(a,backup_a); shutil.copy2(b,backup_b)
        os.replace(a,swap_a); os.replace(b,swap_b)
        os.replace(swap_a,b); os.replace(swap_b,a)
        # Exchange the file objects while keeping each original path's bytes intact.
        for destination,source_copy in ((a,backup_a),(b,backup_b)):
            os.chmod(destination,os.stat(destination).st_mode | stat.S_IWRITE)
            shutil.copyfile(source_copy,destination)
            shutil.copystat(source_copy,destination)
    except Exception:
        for destination,source_copy in ((a,backup_a),(b,backup_b)):
            if os.path.exists(source_copy):
                try:
                    if os.path.exists(destination):
                        os.chmod(destination,os.stat(destination).st_mode | stat.S_IWRITE)
                    shutil.copy2(source_copy,destination)
                except OSError:
                    pass
        raise
    finally:
        for path in (backup_a,backup_b,swap_a,swap_b):
            try:
                if os.path.isfile(path):
                    os.chmod(path,os.stat(path).st_mode | stat.S_IWRITE)
                    os.remove(path)
            except OSError:
                pass


def _cmd_add(self, args, out):
    if not args:
        out.write([("Usage: add /f|/d name | /link name target | -del|-copy|-move|-ren|-rplc|-crplc|-frplc|-s", "plain")]); return
    op = args[0].lower()
    required={"/f":2,"/d":2,"/link":3,"-del":2,"-delete":2,
              "-copy":3,"-move":3,"-ren":3,"-rplc":3,
              "-crplc":3,"-crpc":3,"-frplc":3,"-s":2}
    if op not in required:
        out.write([(f"add: unknown operation or attribute: {args[0]}","error")]); return
    if len(args)<required[op]:
        out.write([(f"add: missing operand for {op}","error")]); return
    fixed_arity={"/link":3,"-copy":3,"-move":3,"-ren":3,"-rplc":3,
                 "-crplc":3,"-crpc":3,"-frplc":3}
    if op in fixed_arity and len(args)>fixed_arity[op]:
        out.write([(f"add: unexpected argument for {op}; quote paths containing spaces", "error")]); return
    try:
        if op in ("/f", "/d") and len(args) >= 2:
            path = _resolve(self, " ".join(args[1:]))
            Path(path).touch(exist_ok=False) if op == "/f" else os.makedirs(path, exist_ok=False)
        elif op == "/link" and len(args) >= 3:
            os.symlink(_resolve(self, args[2]), _resolve(self, args[1]))
        elif op in ("-del", "-delete") and len(args) >= 2:
            path = _resolve(self, " ".join(args[1:]))
            shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
        elif op in ("-copy", "-move", "-ren", "-rplc", "-crplc", "-crpc", "-frplc") and len(args) >= 3:
            a, b = _resolve(self, args[1]), _resolve(self, args[2])
            if op == "-copy": shutil.copy2(a, b) if os.path.isfile(a) else shutil.copytree(a, b)
            elif op == "-move": shutil.move(a, b)
            elif op == "-ren": os.replace(a, b)
            elif op == "-rplc":
                _swap_file_objects_keep_path_data(a,b)
            elif op in ("-crplc", "-crpc"):
                da, db = Path(a).read_bytes(), Path(b).read_bytes()
                Path(a).write_bytes(db); Path(b).write_bytes(da)
            else:
                temp = a + ".xsh-content-tmp"; shutil.copy2(a, temp)
                try: shutil.copy2(b, a); shutil.copy2(temp, b)
                finally:
                    if os.path.exists(temp): os.remove(temp)
        elif op == "-s" and len(args) >= 2:
            pattern = " ".join(args[1:]).lower()
            for root, dirs, files in os.walk(self.cwd):
                for name in dirs + files:
                    if fnmatch.fnmatch(name.lower(), pattern): out.write([(os.path.join(root, name), "plain")])
        else:
            out.write([("add: unknown operation or missing arguments", "error")]); return
    except (OSError, shutil.Error) as exc: out.write([(f"add: {exc}", "error")])


def _cmd_write(self, args, out):
    if not args:
        out.write([("Usage: write -nw file text | -ow file text | -lock/-unlock/-lockr/-unlockr/-alock/-aunlock file", "plain")]); return
    op=args[0].lower()
    supported={"-nw","-ow","-lock","-unlock","-lockr","-unlockr","-alock","-aunlock"}
    if op not in supported:
        out.write([(f"write: unknown attribute: {args[0]}","error")]); return
    if len(args)<2:
        out.write([(f"write: missing file name for {op}","error")]); return
    if op in ("-nw","-ow") and len(args)<3:
        out.write([("write: text is required", "error")]); return
    if op not in ("-nw","-ow") and len(args)>2:
        out.write([(f"write: unexpected argument for {op}", "error")]); return
    op, path = op, _resolve(self, args[1])
    try:
        if op in ("-nw", "-ow"):
            if len(args) < 3:
                out.write([("write: text is required", "error")]); return
            if op == "-ow" and not os.path.isfile(path):
                out.write([("write: target file does not exist", "error")]); return
            with open(path, "x" if op == "-nw" else "w", encoding="utf-8") as f: f.write(" ".join(args[2:]))
            return
        if not os.path.exists(path):
            out.write([("write: file not found", "error")]); return
        if os.name == "nt":
            user = os.environ.get("USERNAME", "Everyone")
            rights = {"-lock":"W", "-unlock":"W", "-lockr":"R", "-unlockr":"R", "-alock":"R,W", "-aunlock":"R,W"}
            if op not in rights: out.write([("write: unknown attribute", "error")]); return
            locked = op in ("-lock", "-lockr", "-alock")
            action = "/deny" if locked else "/remove:d"
            ace = f"{user}:({rights[op]})" if locked else user
            result = subprocess.run(["icacls", path, action, ace], capture_output=True, text=True)
            if result.returncode: raise OSError(result.stderr.strip() or result.stdout.strip())
        else:
            mode = stat.S_IMODE(os.stat(path).st_mode)
            rmask = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            wmask = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
            changes = {"-lock":(0,wmask), "-unlock":(stat.S_IWUSR,0), "-lockr":(0,rmask),
                       "-unlockr":(stat.S_IRUSR,0), "-alock":(0,rmask|wmask),
                       "-aunlock":(stat.S_IRUSR|stat.S_IWUSR,0)}
            if op not in changes: out.write([("write: unknown attribute", "error")]); return
            add, remove = changes[op]; os.chmod(path, (mode | add) & ~remove)
    except OSError as exc: out.write([(f"write: {exc}", "error")])


def _complete_path(self):
    editor = self.editor; buf, pos = editor.buf, editor.pos; left = buf[:pos]
    match = __import__("re").search(r'(?:^|\s)(?:"([^"]*)|([^\s]*))$', left)
    if not match: return
    group = 1 if match.group(1) is not None else 2
    fragment = match.group(group); start = match.start(group)
    directory, prefix = os.path.split(fragment)
    base = _resolve(self.core, directory) if directory else self.core.cwd
    try:
        with os.scandir(base) as it:
            candidates = sorted(e.name for e in it if e.name.lower().startswith(prefix.lower()))
    except OSError: return
    if not candidates: return
    state = getattr(self, "_tab_completion_state", None)
    context = (left[:start], directory)
    if state and state[0] == context and prefix.lower() in (name.lower() for name in state[2]):
        candidates = list(state[2])
        index = (state[1] + 1) % len(candidates)
    else:
        index = 0
    name = candidates[index]
    value = os.path.join(directory, name) if directory else name
    if os.path.isdir(os.path.join(base, name)): value = value.rstrip("/\\") + os.sep
    if any(c.isspace() for c in value): value = '"' + value.rstrip("/\\") + '"'
    updated = left[:start] + value + buf[pos:]
    editor.buf = updated; editor.pos = len(left[:start] + value)
    self._tab_completion_state = (context, index, tuple(candidates))


def _on_key(self, event):
    self._caret_visible=True
    if event.key() == _xsh.Qt.Key.Key_Tab and not self.busy:
        self._complete_path(); self._render_input(); return
    return _original_on_key(self, event)


def _cmd_back(self, args, out):
    parent = os.path.dirname(os.path.normpath(self.cwd))
    if parent and parent != self.cwd:
        self.cwd = self.current = parent
    else:
        out.write([("back: already at the root directory", "dim")])


def _cmd_setting(self, args, out):
    callback = getattr(self, "open_settings_callback", None)
    if callback: callback()
    else: out.write([("Settings are not available in the recovered core.", "plain")])


def _cmd_read(self, args, out):
    if not args:
        out.write([("Usage: read <file> | read -boot <file or directory>", "plain")]); return
    boot=args[0].lower() in ("-boot","-b")
    if args[0].startswith("-") and not boot:
        out.write([(f"read: unknown attribute: {args[0]}","error")]); return
    target=" ".join(args[1:] if boot else args).strip().strip("\"'")
    if not target:
        out.write([("read: element name is required", "error")]); return
    path=_resolve(self,target)
    if not os.path.exists(path):
        out.write([(f"read: element not found: {target}","error")]); return
    if boot:
        _launch(self,path,out)
        return
    if not os.path.isfile(path):
        out.write([("read: target is not a file; use read -boot to open a directory", "error")]); return
    try:
        try:
            with open(path,"r",encoding="utf-8-sig",newline=None) as stream: content=stream.read()
        except UnicodeDecodeError:
            with open(path,"r",encoding="cp1251",newline=None) as stream: content=stream.read()
        out.write([(f"--- {os.path.basename(path)} ---","dim")])
        if content:
            for line in content.splitlines(): out.write([(line,"plain")])
        else:
            out.write([("(empty file)","dim")])
        out.write([])
    except (OSError,UnicodeError) as exc:
        out.write([(f"read: cannot display file: {exc}","error")])


def _cmd_ver(self, args, out):
    out.write([(f"{APP_NAME} v{APP_VERSION}", "cmd")])
    out.write([("\u0413\u0440\u0430\u0444\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043e\u0431\u043e\u043b\u043e\u0447\u043a\u0430 \u0434\u043b\u044f \u043d\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u0438 \u0438 \u0440\u0430\u0431\u043e\u0442\u044b \u0441 \u0444\u0430\u0439\u043b\u0430\u043c\u0438 \u0438 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0430\u043c\u0438.", "plain")])


def _cmd_about(self, args, out):
    callback=getattr(self,"about_callback",None)
    if callback: callback()
    else: out.write([("\u041e \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435: "+APP_NAME+" v"+APP_VERSION,"plain")])


def _show_about(self):
    c = _xsh.C
    dialog = QDialog(self, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
    dialog.setObjectName("aboutDialog")
    dialog.setStyleSheet(
        f"QDialog#aboutDialog {{ background: {c['bg']}; border: 1px solid {c['lav']}; border-radius: 6px; }}"
        f"QLabel {{ color: {c['fg']}; }}"
        f"QPushButton {{ background: {c['sel']}; color: {c['fg']}; border: 1px solid {c['lav']};"
        f" padding: 4px 16px; border-radius: 4px; }}"
        f"QPushButton:hover {{ background: {c['cmd']}; color: {c['bg']}; }}"
    )
    lay = QVBoxLayout(dialog)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(6)

    title = QLabel(f"<span style='color:{c['cmd']};font-size:18px;font-weight:bold'>{APP_NAME}</span>"
                   f"<span style='color:{c['dim']};font-size:13px'> v{APP_VERSION}</span>")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(title)

    desc = QLabel("Графическая командная оболочка для файловой системы.")
    desc.setStyleSheet(f"color:{c['dim']};font-size:12px")
    desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desc.setWordWrap(True)
    lay.addWidget(desc)

    line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color:{c['lav']};")
    line.setFixedHeight(1)
    lay.addWidget(line)

    footer = QLabel(f"<span style='color:{c['teal']}'>xshcli</span> <span style='color:{c['dim']}'>v2.0</span>")
    footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(footer)

    btn = QPushButton("OK")
    btn.setDefault(True)
    btn.clicked.connect(dialog.accept)
    lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(24)
    shadow.setColor(QColor(0, 0, 0, 160))
    shadow.setOffset(0, 6)
    dialog.setGraphicsEffect(shadow)

    dialog.adjustSize()
    host = self.window()
    center = host.mapToGlobal(host.rect().center())
    dialog.move(center.x() - dialog.width() // 2, center.y() - dialog.height() // 2)
    dialog.exec()


def _cmd_readme(self,args,out):
    if args:
        out.write([(f"readme: unexpected argument: {args[0]}","error")]); return
    candidates=(os.path.join(APP_DIR,"readme.xmdf"), os.path.join(APP_DIR,"cache","readme.xmdf"),
                os.path.join(BUNDLE_DIR,"readme.xmdf"))
    path=next((c for c in candidates if os.path.isfile(c)),candidates[0])
    try:
        with open(path,"r",encoding="utf-8") as stream:
            for line in stream: out.write([(line.rstrip("\r\n"),"plain")])
    except OSError as exc:
        out.write([(f"readme: {exc}","error")])


def _cmd_xmd(self,args,out):
    if args:
        out.write([(f"xmd: unknown attribute: {args[0]}","error")]); return
    callback=getattr(self,"open_commander_callback",None)
    if callback: callback()
    else: out.write([("xmd: XMD Commander is not available","error")])


def _start_session(self):
    if getattr(self.core, "settings", {}).get("debug", True):
        self._emit([("[xmdinfo:0001] Debug mode is active", "plain")])
    self._new_prompt()


_rows = [
('plain','\u041d\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u044f'),
('plain','  cd <path>                 \u043f\u0435\u0440\u0435\u0439\u0442\u0438 \u0432 \u043a\u0430\u0442\u0430\u043b\u043e\u0433 \u0438\u043b\u0438 \u0432\u044b\u0431\u0440\u0430\u0442\u044c \u0444\u0430\u0439\u043b'),
('plain','  xsh [path]                \u0441\u043f\u0438\u0441\u043e\u043a \u0444\u0430\u0439\u043b\u043e\u0432 \u0438 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u043e\u0432'),
('plain','  pwd                       \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u043a\u0430\u0442\u0430\u043b\u043e\u0433'),
('plain','  ver | version             \u0432\u0435\u0440\u0441\u0438\u044f \u0438 \u043a\u0440\u0430\u0442\u043a\u043e\u0435 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435'),
('plain','  back                      \u043f\u0435\u0440\u0435\u0445\u043e\u0434 \u0432 \u0440\u043e\u0434\u0438\u0442\u0435\u043b\u044c\u0441\u043a\u0443\u044e \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044e'),
('plain','  help                      \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u044d\u0442\u0443 \u0441\u043f\u0440\u0430\u0432\u043a\u0443'),
('plain','  about                     \u043e\u043a\u043d\u043e \u00ab\u041e \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435\u00bb'),
('plain','  clear | cls               \u043e\u0447\u0438\u0441\u0442\u0438\u0442\u044c \u044d\u043a\u0440\u0430\u043d'),
('plain','  exit | quit               \u0437\u0430\u043a\u0440\u044b\u0442\u044c \u043e\u0431\u043e\u043b\u043e\u0447\u043a\u0443'),
('plain','  setting                   \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438'),
('plain','  xmd                       \u043e\u0442\u043a\u0440\u044b\u0442\u044c XMD Commander (Esc / Ctrl+Q \u2014 \u043d\u0430\u0437\u0430\u0434)'),('plain','  readme                    \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c readme.xmdf'),
('plain',''),('plain','\u041e\u043f\u0435\u0440\u0430\u0446\u0438\u0438'),
('plain','  add /f|/d <name>          \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0444\u0430\u0439\u043b \u0438\u043b\u0438 \u043a\u0430\u0442\u0430\u043b\u043e\u0433'),
('plain','  add /link <name> <target> \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443'),
('plain','  add -del <path>            \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u044d\u043b\u0435\u043c\u0435\u043d\u0442'),
('plain','  add -copy <A> <B>          \u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c A \u0432 B'),
('plain','  add -move <A> <B>          \u043f\u0435\u0440\u0435\u043c\u0435\u0441\u0442\u0438\u0442\u044c A \u0432 B'),
('plain','  add -ren <A> <B>           \u043f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u0442\u044c A \u0432 B'),
('plain','  add -rplc <A> <B>          \u043e\u0431\u043c\u0435\u043d\u044f\u0442\u044c \u0444\u0430\u0439\u043b\u044b \u043c\u0435\u0441\u0442\u0430\u043c\u0438 (\u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u0437\u0430\u043f\u0438\u0441\u0438 \u0434\u0430\u043d\u043d\u044b\u0445)'),
('plain','  add -crplc <A> <B>         \u043e\u0431\u043c\u0435\u043d\u044f\u0442\u044c \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u043c\u043e\u0435'),
('plain','  add -frplc <A> <B>         \u043e\u0431\u043c\u0435\u043d\u044f\u0442\u044c \u0434\u0430\u043d\u043d\u044b\u0435 \u0438 \u043c\u0435\u0441\u0442\u0430'),
('plain','  add -s <mask>              \u043d\u0430\u0439\u0442\u0438 \u0444\u0430\u0439\u043b\u044b'),
('plain','  read <file>                \u0432\u044b\u0432\u0435\u0441\u0442\u0438 \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u043c\u043e\u0435 \u0444\u0430\u0439\u043b\u0430 \u0432 \u043e\u0431\u043e\u043b\u043e\u0447\u043a\u0435'),('plain','  read -boot <path>          \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0444\u0430\u0439\u043b \u0438\u043b\u0438 \u043a\u0430\u0442\u0430\u043b\u043e\u0433'),('plain','  write -nw <file> <text>    \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0438 \u0437\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u0444\u0430\u0439\u043b'),
('plain','  write -ow <file> <text>    \u0437\u0430\u043c\u0435\u043d\u0438\u0442\u044c \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u043c\u043e\u0435'),
('plain','  write -lock/-unlock <file> \u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u043a\u0430 \u0437\u0430\u043f\u0438\u0441\u0438'),
('plain','  write -lockr/-unlockr <file> \u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u043a\u0430 \u0447\u0442\u0435\u043d\u0438\u044f'),
('plain','  write -alock/-aunlock <file> \u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u043a\u0430 \u0447\u0442\u0435\u043d\u0438\u044f \u0438 \u0437\u0430\u043f\u0438\u0441\u0438'),
('plain',''),('plain','\u0410\u0442\u0440\u0438\u0431\u0443\u0442\u044b'),
('plain','  xsh -l                     \u043f\u043e\u0434\u0440\u043e\u0431\u043d\u044b\u0439 \u0441\u043f\u0438\u0441\u043e\u043a'),
('plain','  xsh -a                     \u0430\u0431\u0441\u043e\u043b\u044e\u0442\u043d\u044b\u0435 \u043f\u0443\u0442\u0438'),
('plain','  xsh -set <name>             \u0441\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u043e\u0431 \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u0435'),
('plain','  xsh -v <name>               \u0434\u0430\u0442\u044b \u0444\u0430\u0439\u043b\u043e\u0432\u043e\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u044b'),
('plain','  xsh -boot <name>            \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0444\u0430\u0439\u043b \u0438\u043b\u0438 \u0432\u043e\u0439\u0442\u0438 \u0432 \u043a\u0430\u0442\u0430\u043b\u043e\u0433'),
('plain','  xsh -del <name>             \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0444\u0430\u0439\u043b \u0438\u043b\u0438 \u043a\u0430\u0442\u0430\u043b\u043e\u0433'),
('plain','  Tab                         \u0430\u0432\u0442\u043e\u0434\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435'),
('dim','-set, -boot \u0438 -del \u043e\u0442\u043d\u043e\u0441\u044f\u0442\u0441\u044f \u043a \u043e\u0434\u043d\u043e\u043c\u0443 \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u0443.')]
_rows = list(_rows)
_xsh.HELP_LINES = (("plain", f"{_xsh.APP_NAME} v{_xsh.APP_VERSION}"), ("plain", "")) + tuple(_rows)

_xsh.ShellCore._resolve = _resolve
_xsh.ShellCore._cmd_list = _cmd_list
_xsh.ShellCore._cmd_add = _cmd_add
_xsh.ShellCore._cmd_write = _cmd_write
_xsh.ShellCore._cmd_setting = _cmd_setting
_xsh.ShellCore._cmd_back = _cmd_back
_xsh.ShellCore._cmd_xmdREADME = _cmd_xmd
_xsh.ShellCore._cmd_readme = _cmd_readme
_xsh.ShellCore._cmd_ver = _cmd_ver
_xsh.ShellCore._cmd_read = _cmd_read
_xsh.ShellCore._cmd_about = _cmd_about
_xsh.DEBUG_MODE = True
_xsh.STARTUP_DIR = "C:\\"
_xsh.XshWindow.start_session = _start_session
_original_core_init = _xsh.ShellCore.__init__
def _core_init(self, *args, **kwargs):
    _original_core_init(self, *args, **kwargs)
    self.builtins.update({"add": self._cmd_add, "write": self._cmd_write,
                          "setting": self._cmd_setting, "xmd": self._cmd_xmdREADME,
                          "readme": self._cmd_readme, "back": self._cmd_back})
_xsh.ShellCore.__init__ = _core_init
_original_on_key = _xsh.XshWindow._on_key
_xsh.XshWindow._complete_path = _complete_path
_xsh.XshWindow._on_key = _on_key


SETTINGS_FILE = os.path.join(APP_DIR, "data", "xmd", "settings.json")
SETTINGS_DEFAULTS = {"font":"Consolas", "palette":"Default (XMD)", "size":7,
                     "transparency":0, "chcp":"866", "hide_console":True,
                     "startup_dir":"C:\\", "debug":True}
WINDOW_SIZES = ((640,320),(800,450),(1024,576),(1280,720),(1366,768),
                (1600,900),(1920,1080),(0,0))
PALETTES = {
 "Default (XMD)":{"bg":"#1a1c28","fg":"#ffffff","lav":"#b9bbd2","dim":"#a9abc4","dir":"#c9e2fc","cmd":"#a6d6ee","pink":"#c677a2","yellow":"#fdffec","teal":"#8fd8cd","date":"#b9d0ee","perm_r":"#bcdcf3","caret":"#a8aecf","sel":"#33384f","red":"#ff5f57","amber":"#febc2e","green":"#28c840"},
 "Standard (CMD)":{"bg":"#0c0c0c","fg":"#cccccc","lav":"#aaaaaa","dim":"#888888","dir":"#569cd6","cmd":"#cccccc","pink":"#f44747","yellow":"#dcdcaa","teal":"#4ec9b0","date":"#9cdcfe","perm_r":"#cccccc","caret":"#cccccc","sel":"#264f78","red":"#f44747","amber":"#d7ba7d","green":"#6a9955"},
 "Matrix/Hacker":{"bg":"#020b02","fg":"#39ff14","lav":"#20c20e","dim":"#16850a","dir":"#66ff66","cmd":"#39ff14","pink":"#00cc44","yellow":"#aaff00","teal":"#00ff99","date":"#4dff4d","perm_r":"#20c20e","caret":"#39ff14","sel":"#073d10","red":"#55ff55","amber":"#aaff00","green":"#00ff66"}}


def _load_preferences():
    try:
        with open(SETTINGS_FILE,"r",encoding="utf-8") as stream:
            saved=json.load(stream)
        return {**SETTINGS_DEFAULTS, **saved} if isinstance(saved,dict) else dict(SETTINGS_DEFAULTS)
    except (OSError,ValueError):
        return dict(SETTINGS_DEFAULTS)


def _save_preferences(core):
    os.makedirs(os.path.dirname(SETTINGS_FILE),exist_ok=True)
    with open(SETTINGS_FILE,"w",encoding="utf-8") as stream:
        json.dump(core.settings,stream,ensure_ascii=False,indent=2)


def _available_fonts():
    installed=set(_xsh.QFontDatabase.families())
    preferred=getattr(_xsh,"FONT_CANDIDATES",("Consolas","Cascadia Mono","Courier New","Lucida Console"))
    fonts=[name for name in preferred if name in installed]
    if not fonts:
        fonts=[_xsh.QFontDatabase.systemFont(_xsh.QFontDatabase.SystemFont.FixedFont).family()]
    return fonts


def _core_init_with_settings(self,*args,**kwargs):
    _original_core_init(self,*args,**kwargs)
    self.settings=_load_preferences()
    startup=self.settings.get("startup_dir") or SETTINGS_DEFAULTS["startup_dir"]
    if os.path.isdir(startup): self.cwd=self.current=self.home=os.path.abspath(startup)
    self.builtins.update({"add":self._cmd_add,"write":self._cmd_write,
                          "setting":self._cmd_setting,"xmd":self._cmd_xmdREADME,
                          "readme":self._cmd_readme,"back":self._cmd_back,
                          "ver":self._cmd_ver,"version":self._cmd_ver,"about":self._cmd_about,"read":self._cmd_read})
    self.open_settings_callback=None
    self.about_callback=None


def _window_init_with_settings(self,core):
    _original_window_init(self,core)
    icon_path=next((p for p in (os.path.join(BUNDLE_DIR,"xmd.ico"),os.path.join(APP_DIR,"xmd.ico"))
                    if os.path.isfile(p)),None)
    if icon_path: self.setWindowIcon(QIcon(icon_path))
    core.settings=getattr(core,"settings",_load_preferences())
    self.settings_button=QPushButton("\u2699",self)
    self.settings_button.setToolTip("Settings")
    self.settings_button.clicked.connect(self.toggle_settings)
    self._build_settings_panel()
    self._commander_active=False
    self.commander_panel=CommanderPanel(core.cwd,embedded=True,parent=self)
    self.commander_panel.exit_requested.connect(self.return_from_commander)
    self.commander_panel.cwd_changed.connect(self._commander_path_changed)
    self.commander_panel.set_shell(self._commander_shell,COMMANDER_COMMANDS)
    self.commander_panel.hide()
    core.open_settings_callback=self.toggle_settings
    core.open_commander_callback=self.open_commander
    core.about_callback=self.show_about
    self._layout()
    self._apply_settings()
    self.setCursor(Qt.CursorShape.ArrowCursor)
    self.view.setCursor(Qt.CursorShape.ArrowCursor)
    self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
    self._caret_visible=True
    self.caret_timer=_xsh.QTimer(self)
    self.caret_timer.setInterval(500)
    self.caret_timer.timeout.connect(self._toggle_console_caret)
    self.caret_timer.start()
    self._render_input()


def _show_about_from_window(self):
    _show_about(self)


def _toggle_console_caret(self):
    if self.busy: return
    scrollbar=self.view.verticalScrollBar()
    previous_scroll=scrollbar.value()
    was_at_bottom=previous_scroll >= scrollbar.maximum()
    self._caret_visible=not self._caret_visible
    self._render_input()
    if not was_at_bottom:
        scrollbar.setValue(previous_scroll)


def _render_input_with_blink(self):
    fmt=self.fmt_caret
    fmt.setBackground(QColor(_xsh.C["caret"]) if self._caret_visible else QColor(0,0,0,0))
    fmt.setForeground(QColor(_xsh.C["bg"]) if self._caret_visible else QColor(_xsh.C["cmd"]))
    _original_render_input(self)


def _build_settings_panel(self):
    panel=QWidget(self); panel.setObjectName("xmdSettingsPanel"); panel.setFixedWidth(292)
    body=QWidget(panel); body.setObjectName("xmdSettingsBody"); layout=QVBoxLayout(body)
    layout.setContentsMargins(14,10,14,10); layout.setSpacing(7)
    header=QHBoxLayout(); title=QLabel("XMD | SETTINGS")
    title.setStyleSheet(f"color:{_xsh.C['cmd']};font-weight:bold")
    close=QPushButton("X"); close.setFixedWidth(28); close.clicked.connect(self.toggle_settings)
    header.addWidget(title); header.addStretch(1); header.addWidget(close); layout.addLayout(header)
    def section(text):
        label=QLabel(text); label.setStyleSheet(f"color:{_xsh.C['teal']};font-weight:bold;margin-top:5px")
        layout.addWidget(label)
    section("\u0428\u0440\u0438\u0444\u0442")
    self.font_combo=QComboBox(); self.font_combo.addItems(_available_fonts())
    self.font_combo.currentTextChanged.connect(lambda value:self._change_setting("font",value))
    layout.addWidget(self.font_combo)
    section("\u0426\u0432\u0435\u0442\u043e\u0432\u0430\u044f \u043f\u0430\u043b\u0438\u0442\u0440\u0430")
    self.palette_combo=QComboBox(); self.palette_combo.addItems(tuple(PALETTES))
    self.palette_combo.currentTextChanged.connect(lambda value:self._change_setting("palette",value))
    layout.addWidget(self.palette_combo)
    section("\u0420\u0430\u0437\u043c\u0435\u0440 \u043e\u043a\u043d\u0430")
    self.size_combo=QComboBox()
    for width,height in WINDOW_SIZES:
        self.size_combo.addItem("Fullscreen" if not width else f"{width} x {height}")
    self.size_combo.currentIndexChanged.connect(lambda value:self._change_setting("size",value))
    layout.addWidget(self.size_combo)
    section("Transparency 0-50%")
    row=QHBoxLayout(); self.transparency_slider=QSlider(Qt.Orientation.Horizontal)
    self.transparency_slider.setRange(0,5); self.transparency_label=QLabel("0%")
    self.transparency_slider.valueChanged.connect(self._change_transparency)
    row.addWidget(self.transparency_slider,1); row.addWidget(self.transparency_label); layout.addLayout(row)
    section("\u0420\u0435\u0436\u0438\u043c \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u0447\u0438\u043a\u0430")
    self.debug_check=QCheckBox("Debug mode")
    self.debug_check.toggled.connect(lambda value:self._change_setting("debug",bool(value)))
    layout.addWidget(self.debug_check)
    self.hide_console_check=QCheckBox("Hide debug console")
    self.hide_console_check.toggled.connect(lambda value:self._change_setting("hide_console",bool(value)))
    layout.addWidget(self.hide_console_check)
    self.chcp_combo=QComboBox(); self.chcp_combo.addItems(("866 - RU DOS","1251 - RU Windows","437 - EN DOS","1252 - EN Windows","Custom"))
    self.chcp_combo.currentIndexChanged.connect(self._change_chcp)
    layout.addWidget(self.chcp_combo)
    self.chcp_custom=QLineEdit(); self.chcp_custom.setPlaceholderText("Custom code page, e.g. cp866")
    self.chcp_custom.editingFinished.connect(lambda:self._change_setting("chcp",self.chcp_custom.text().strip()))
    layout.addWidget(self.chcp_custom)
    section("Startup directory")
    self.startup_edit=QLineEdit(); self.startup_edit.editingFinished.connect(self._save_startup_directory)
    layout.addWidget(self.startup_edit); layout.addStretch(1)
    scroll=QScrollArea(panel); scroll.setWidgetResizable(True); scroll.setWidget(body)
    scroll.setFrameShape(_xsh.QFrame.Shape.NoFrame)
    outer=QVBoxLayout(panel); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)
    self.settings_panel=panel; panel.hide(); self._settings_previous_size=None
    self._settings_previous_size_index=None
    self._style_settings_panel()


def _style_settings_panel(self):
    self.settings_panel.setFont(self.font_r)
    bg = _xsh.C['bg']; fg = _xsh.C['fg']; field = _xsh.C['sel']; accent = _xsh.C['cmd']
    self.settings_panel.setStyleSheet(
        f"QWidget#xmdSettingsPanel, QWidget#xmdSettingsBody, QScrollArea, QScrollArea QWidget "
        f"{{background-color:{bg};color:{fg};}} "
        f"QWidget#xmdSettingsPanel {{border-left:1px solid {_xsh.C['lav']};}} "
        f"QLabel, QCheckBox {{color:{fg};background:transparent;}} "
        f"QComboBox, QLineEdit {{background-color:{field};color:{fg};border:1px solid {_xsh.C['lav']};padding:5px;}} "
        f"QComboBox QAbstractItemView {{background-color:{field};color:{fg};selection-background-color:{accent};selection-color:{bg};}} "
        f"QPushButton {{background-color:{field};color:{fg};border:0;padding:4px;}} "
        f"QSlider::groove:horizontal {{height:4px;background:{field};}} "
        f"QSlider::handle:horizontal {{width:12px;background:{accent};margin:-4px 0;}}"
    )


def _toggle_settings(self):
    opening=not self.settings_panel.isVisible()
    if opening:
        self._settings_previous_size=self.size()
        self._settings_previous_size_index=int(self.core.settings.get("size",7))
        if self.width()<760: self.resize(760,self.height())
        self.settings_panel.show(); self._refresh_settings_controls()
    else:
        self.settings_panel.hide()
        current_index=int(self.core.settings.get("size",7))
        if (self._settings_previous_size is not None and
                current_index==self._settings_previous_size_index):
            self.resize(self._settings_previous_size)
        self._settings_previous_size=None
        self._settings_previous_size_index=None
    self._layout()


def _refresh_settings_controls(self):
    values=((self.font_combo,self.core.settings.get("font","Consolas")),
            (self.palette_combo,self.core.settings.get("palette","Default (XMD)")),
            (self.size_combo,int(self.core.settings.get("size",7))))
    for widget,value in values:
        widget.blockSignals(True)
        index=value if isinstance(value,int) else widget.findText(str(value))
        widget.setCurrentIndex(max(0,min(index,widget.count()-1)))
        widget.blockSignals(False)
    transparency=max(0,min(5,int(self.core.settings.get("transparency",0))))
    self.transparency_slider.blockSignals(True); self.transparency_slider.setValue(transparency); self.transparency_slider.blockSignals(False)
    self.transparency_label.setText(f"{transparency*10}%")
    for widget,key in ((self.debug_check,"debug"),(self.hide_console_check,"hide_console")):
        widget.blockSignals(True); widget.setChecked(bool(self.core.settings.get(key,False))); widget.blockSignals(False)
    self.startup_edit.setText(str(self.core.settings.get("startup_dir",SETTINGS_DEFAULTS["startup_dir"])))
    chcp=str(self.core.settings.get("chcp","866"))
    known=("866","1251","437","1252")
    index=known.index(chcp) if chcp in known else 4
    self.chcp_combo.blockSignals(True); self.chcp_combo.setCurrentIndex(index); self.chcp_combo.blockSignals(False)
    self.chcp_custom.setText(chcp if index==4 else "")


def _change_setting(self,key,value):
    if key=="font" and value not in _available_fonts(): return
    self.core.settings[key]=value; _save_preferences(self.core)
    xmd_diagnostics.log_action("settings.change",key=key,value=("<redacted>" if key=="startup_dir" else value))
    if key=="palette":
        _xsh.C.update(PALETTES.get(value,PALETTES["Default (XMD)"]))
        self._apply_theme()
    elif key=="font": self._apply_font(value)
    elif key=="size": self._apply_window_size(int(value))
    elif key=="transparency": self.setWindowOpacity(1.0-int(value)*0.1)
    elif key=="debug": _xsh.DEBUG_MODE=bool(value)
    elif key=="chcp": self.core.settings["chcp"]=str(value)
    self._refresh_settings_controls()


def _change_transparency(self,value):
    self.transparency_label.setText(f"{value*10}%")
    self._change_setting("transparency",int(value))


def _change_chcp(self,index):
    known=("866","1251","437","1252")
    if index<4: self._change_setting("chcp",known[index])
    elif self.chcp_custom.text().strip(): self._change_setting("chcp",self.chcp_custom.text().strip())


def _save_startup_directory(self):
    value=self.startup_edit.text().strip()
    if os.path.isdir(value): self._change_setting("startup_dir",os.path.abspath(value))
    else: self.startup_edit.setText(str(self.core.settings.get("startup_dir",SETTINGS_DEFAULTS["startup_dir"])))


def _apply_font(self,family):
    size=self.size(); self.font_r.setFamily(family); self.font_b=QFont(self.font_r); self.font_b.setBold(True)
    fm=QFontMetricsF(self.font_r); self.cw=fm.horizontalAdvance("0"); self.lh=float(max(fm.lineSpacing(),round(self.cw*_xsh.LINE_RATIO)))
    self.pad_x=round(self.cw*1.22); self.pad_top=round(self.lh*1.52); self.pad_bottom=round(self.lh*1.34)
    self.view.setFont(self.font_r); self.doc.setDefaultFont(self.font_r)
    for name,(color,bold) in _xsh.STYLE_SPECS.items():
        self.fmt[name].setFont(self.font_b if bold else self.font_r); self.fmt[name].setForeground(QColor(_xsh.C[color]))
    self.fmt_caret.setFont(self.font_r)
    self.resize(size); self._layout(); self._style_settings_panel()


def _apply_theme(self):
    self.view.setStyleSheet(f"QTextEdit {{background:{_xsh.C['bg']};color:{_xsh.C['fg']};border:none;selection-background-color:{_xsh.C['sel']};selection-color:{_xsh.C['fg']};}}")
    for name,(color,bold) in _xsh.STYLE_SPECS.items(): self.fmt[name].setForeground(QColor(_xsh.C[color]))
    self.fmt_caret.setBackground(QColor(_xsh.C["caret"])); self.fmt_caret.setForeground(QColor(_xsh.C["bg"]))
    self._style_settings_panel()
    self.update()


def _apply_window_size(self,index):
    if index==len(WINDOW_SIZES)-1: self.showFullScreen()
    else:
        if self.isFullScreen(): self.showNormal()
        self.resize(*WINDOW_SIZES[max(0,min(index,len(WINDOW_SIZES)-1))])
    self._layout()


def _apply_settings(self):
    settings=self.core.settings
    _xsh.C.update(PALETTES.get(settings.get("palette"),PALETTES["Default (XMD)"]))
    family=settings.get("font","")
    if family in _available_fonts(): _apply_font(self,family)
    self.setWindowOpacity(1.0-max(0,min(5,int(settings.get("transparency",0))))*0.1)
    _xsh.DEBUG_MODE=bool(settings.get("debug",True))
    if self.core.cwd==self.core.home:
        start=settings.get("startup_dir",SETTINGS_DEFAULTS["startup_dir"])
        if os.path.isdir(start): self.core.cwd=self.core.current=self.core.home=os.path.abspath(start)
    _apply_theme(self)
    _apply_window_size(self,int(settings.get("size",7)))
    _refresh_settings_controls(self)


def _window_layout_with_settings(self):
    _original_layout(self)
    if not hasattr(self,"settings_panel"): return
    panel_width=self.settings_panel.width() if self.settings_panel.isVisible() else 0
    self.view.setGeometry(self.pad_x,self.pad_top,max(10,self.width()-2*self.pad_x-panel_width),
                          max(10,self.height()-self.pad_top-self.pad_bottom))
    self.settings_panel.setGeometry(max(0,self.width()-panel_width),0,panel_width,self.height())
    self.settings_button.setGeometry(max(0,self.width()-self.pad_x-32),3,28,25)
    self.settings_button.setStyleSheet(f"QPushButton {{background:transparent;color:{_xsh.C['cmd']};border:0;font-size:16px;}}")
    if hasattr(self,"commander_panel"):
        self.commander_panel.setGeometry(self.view.geometry())
        if self._commander_active:
            self.settings_panel.hide(); self.settings_button.hide()
            self.view.hide(); self.commander_panel.show(); self.commander_panel.raise_()
        else:
            self.commander_panel.hide()
            self.view.show(); self.settings_button.show()
    self.console.columns=max(20,int(self.view.viewport().width()/self.cw))



def _open_commander(self):
    self.settings_panel.hide()
    self._commander_active=True
    self.commander_panel.navigate(self.core.cwd)
    self.view.hide()
    self._layout()
    self.commander_panel.focus_list()
    xmd_diagnostics.log_action("commander.open",path=self.core.cwd)


def _return_from_commander(self):
    self._commander_active=False
    self.commander_panel.hide()
    self.view.show()
    self._layout()
    self.view.setFocus()
    self._render_input()


def _commander_path_changed(self,path):
    if not getattr(self,"_commander_active",False): return
    self.core.cwd=self.core.current=os.path.abspath(path)
    xmd_diagnostics.log_action("commander.cwd",path=self.core.cwd)


COMMANDER_COMMANDS = {
    "cd": ("<path>", "перейти в каталог или выбрать файл"),
    "xsh": ("[path] | -l | -a | -set|-v|-boot|-del <name>", "список файлов и действия с элементом"),
    "pwd": ("", "показать текущий каталог"),
    "back": ("", "переход в родительскую директорию"),
    "add": ("/f|/d|/link|-del|-copy|-move|-ren|-rplc|-crplc|-frplc|-s ...", "операции с файлами и каталогами"),
    "read": ("<file> | -boot <path>", "вывести содержимое файла / открыть файл или каталог"),
    "write": ("-nw|-ow <file> <text> | -lock/-unlock... <file>", "запись и блокировка файлов"),
    "ver": ("", "версия и краткое описание"),
    "version": ("", "версия и краткое описание"),
    "help": ("", "показать справку"),
    "about": ("", "окно «О программе»"),
    "readme": ("", "показать readme.xmdf"),
    "setting": ("", "открыть настройки"),
    "clear": ("", "очистить вывод"),
    "cls": ("", "очистить вывод"),
    "exit": ("", "закрыть xmd"),
    "quit": ("", "закрыть xmd"),
    "xmd": ("", "открыть XMD Commander"),
}


class _PanelOutput:
    def __init__(self,columns):
        self.columns=columns; self.lines=[]; self.cleared=False; self.quit_requested=False
    def write(self,rows): self.lines.append(list(rows or ()))
    def clear(self): self.lines.clear(); self.cleared=True
    def finish(self): pass
    def quit(self): self.quit_requested=True


def _commander_shell(self,line):
    panel=self.commander_panel
    self.core.cwd=self.core.current=panel.cwd
    try:
        word=_xsh.split_args(line)[0].lower()
    except Exception:
        word=""
    if word=="setting":
        self.return_from_commander()
    out=_PanelOutput(max(20,int(panel.editor.viewport().width()/max(1.0,self.cw))))
    self.core.run(line,out)
    if out.quit_requested:
        _xsh.QTimer.singleShot(0,self.close)
    elif self._commander_active:
        panel.navigate(self.core.cwd)
    return out.lines,out.cleared




_original_close_event=_xsh.XshWindow.closeEvent
def _logged_close_event(self,event):
    xmd_diagnostics.log_action("application.close",cwd=getattr(self.core,"cwd",""))
    return _original_close_event(self,event)



_original_window_init=_xsh.XshWindow.__init__
_original_layout=_xsh.XshWindow._layout
_xsh.XshWindow.__init__=_window_init_with_settings
_xsh.XshWindow._layout=_window_layout_with_settings
_xsh.XshWindow.toggle_settings=_toggle_settings
_xsh.XshWindow._style_settings_panel=_style_settings_panel
_original_render_input = _xsh.XshWindow._render_input
_xsh.XshWindow._render_input = _render_input_with_blink
_xsh.XshWindow._toggle_console_caret = _toggle_console_caret
_xsh.XshWindow.show_about = _show_about_from_window
_xsh.XshWindow.open_commander = _open_commander
_xsh.XshWindow.return_from_commander = _return_from_commander
_xsh.XshWindow._commander_path_changed = _commander_path_changed
_xsh.XshWindow._commander_shell = _commander_shell
_xsh.XshWindow.closeEvent = _logged_close_event
_xsh.XshWindow._build_settings_panel=_build_settings_panel
_xsh.XshWindow._refresh_settings_controls=_refresh_settings_controls
_xsh.XshWindow._change_setting=_change_setting
_xsh.XshWindow._change_transparency=_change_transparency
_xsh.XshWindow._change_chcp=_change_chcp
_xsh.XshWindow._save_startup_directory=_save_startup_directory
_xsh.XshWindow._apply_font=_apply_font
_xsh.XshWindow._apply_theme=_apply_theme
_xsh.XshWindow._apply_window_size=_apply_window_size
_xsh.XshWindow._apply_settings=_apply_settings
_xsh.ShellCore.__init__=_core_init_with_settings
_original_core_init=_original_core_init


_original_core_run=_xsh.ShellCore.run
_NO_ARGUMENT_COMMANDS={"pwd","back","help","clear","cls","exit","quit",
                       "ver","version","about","setting","xmd","readme"}

def _validated_run(self,line,out):
    command_line=line.strip()
    if not command_line:
        return _original_core_run(self,line,out)
    try:
        argv=_xsh.split_args(command_line)
    except Exception as exc:
        out.write([(f"xmd: invalid command syntax: {exc}","error")])
        out.finish()
        return
    if not argv:
        return _original_core_run(self,line,out)
    command=argv[0].lower()
    if not _xsh.re.fullmatch(r"[A-Za-z]:",command_line) and command not in self.builtins:
        out.write([(f"xmd: unknown command: {argv[0]}","error")])
        out.finish()
        return
    if command=="cd" and len(argv)>1 and argv[1].startswith("-"):
        out.write([(f"cd: unknown attribute: {argv[1]}","error")])
        out.finish()
        return
    if command in _NO_ARGUMENT_COMMANDS and len(argv)>1:
        out.write([(f"xmd: {argv[0]} does not accept attributes or arguments", "error")])
        out.finish()
        return
    return _original_core_run(self,line,out)


class _LoggedOutput:
    def __init__(self,target,command,cwd): self._target=target; self._command=command; self._cwd=cwd
    def write(self,rows):
        for row in rows or ():
            if isinstance(row,(list,tuple)) and len(row)>1 and row[1]=="error":
                xmd_diagnostics.log_error("command.error",command=self._command,cwd=self._cwd,message=row[0])
        return self._target.write(rows)
    def finish(self): return self._target.finish()
    def __getattr__(self,name): return getattr(self._target,name)


def _logged_run(self,line,out):
    try:
        argv=_xsh.split_args(line)
    except Exception:
        argv=[]
    command_record=line.strip()
    if len(argv)>=3 and argv[0].lower()=="write" and argv[1].lower() in ("-nw","-ow"):
        command_record=f"write {argv[1]} {argv[2]} <content redacted>"
    cwd=getattr(self,"cwd","")
    xmd_diagnostics.log_action("command",command=command_record,cwd=cwd)
    wrapped=_LoggedOutput(out,command_record,cwd)
    try:
        return _validated_run(self,line,wrapped)
    except Exception as exc:
        xmd_diagnostics.log_error("command.exception",command=command_record,cwd=cwd,error=repr(exc))
        raise

_xsh.ShellCore.run=_logged_run

def _run_application():
    settings=_load_preferences()
    startup=settings.get("startup_dir",SETTINGS_DEFAULTS["startup_dir"])
    if os.path.isdir(startup): os.chdir(startup)
    if os.name=="nt" and settings.get("hide_console",True):
        try:
            import ctypes
            handle=ctypes.windll.kernel32.GetConsoleWindow()
            if handle: ctypes.windll.user32.ShowWindow(handle,0)
        except Exception: pass
    _xsh.main()

if __name__ == "__main__":
    _run_application()

