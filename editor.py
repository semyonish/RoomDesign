"""Room editor: change palette colors and see a Blender preview of the chosen camera.

    .venv/bin/python editor.py [rooms/apartment.json]

Colors are written straight into the config's "palette" (formatting kept), then render.py runs
as a separate process so the window stays responsive.
"""

import json
import re
import sys
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "bin" / "python"
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
RENDERED = re.compile(r"^rendered \S+ on .* in ([\d.]+)s -> (.+\.png)$", re.M)


def palette_body(text):
    """Character range of the body of the top-level "palette" object."""
    m = re.search(r'"palette"\s*:\s*\{', text)
    if not m:
        raise ValueError("в конфиге нет палитры")
    depth, i = 1, m.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return m.end(), i - 1


def set_palette_color(text, name, value):
    a, b = palette_body(text)
    body, n = re.subn(rf'("{re.escape(name)}"\s*:\s*")#[0-9A-Fa-f]{{6}}(")', rf"\g<1>{value}\g<2>", text[a:b], count=1)
    if not n:
        raise ValueError(f"цвет {name} не найден в палитре")
    return text[:a] + body + text[b:]


def color_usage(cfg, name):
    """Top-level sections that reference "@name", e.g. walls, doors, furniture: wardrobe."""
    ref, found = f"@{name}", []

    def walk(node):
        if isinstance(node, dict):
            return any(walk(v) for v in node.values())
        if isinstance(node, list):
            return any(walk(v) for v in node)
        return node == ref

    for key, value in cfg.items():
        if key == "palette":
            continue
        if isinstance(value, list):
            kinds = sorted({item.get("type") or item.get("kind") or key for item in value
                            if isinstance(item, dict) and walk(item)})
            found += [f"{key}: {k}" if k != key else key for k in kinds]
        elif walk(value):
            found.append(key)
    return ", ".join(found) or "не используется"


class ImageView(QLabel):
    def __init__(self):
        super().__init__("Здесь появится рендер")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(480, 360)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._pixmap = None

    def show_image(self, path):
        self._pixmap = QPixmap(str(path))
        self._rescale()

    def resizeEvent(self, event):
        self._rescale()
        super().resizeEvent(event)

    def _rescale(self):
        if self._pixmap and not self._pixmap.isNull():
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class Editor(QMainWindow):
    def __init__(self, config_path):
        super().__init__()
        self.proc = None
        self.pending = False
        self.debounce = QTimer(self, singleShot=True, interval=400, timeout=self.render)
        self.clock = QElapsedTimer()
        self.ticker = QTimer(self, interval=200, timeout=self._tick)

        self.file_label = QLabel()
        open_btn = QPushButton("Открыть…", clicked=self.open_file)
        self.palette_box = QGroupBox("Палитра")
        self.palette_form = QFormLayout(self.palette_box)
        self.camera = QComboBox(currentIndexChanged=self.changed)
        self.clay = QCheckBox("Без цветов (глина)", toggled=self.changed)
        self.quality = QComboBox(currentIndexChanged=self.changed)
        self.quality.addItems(["Черновик (секунды)", "Проверка (~30 с)", "Финал (минуты)"])
        self.auto = QCheckBox("Рендерить при каждом изменении", checked=True)
        render_btn = QPushButton("Рендер", clicked=self.render)
        revert_btn = QPushButton("Вернуть цвета как при открытии", clicked=self.revert)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        top = QHBoxLayout()
        top.addWidget(self.file_label, 1)
        top.addWidget(open_btn)
        side = QVBoxLayout()
        side.addLayout(top)
        side.addWidget(self.palette_box)
        side.addWidget(QLabel("Камера"))
        side.addWidget(self.camera)
        side.addWidget(QLabel("Качество"))
        side.addWidget(self.quality)
        for w in (self.clay, self.auto, render_btn, revert_btn):
            side.addWidget(w)
        side.addStretch(1)
        side.addWidget(self.status)
        panel = QWidget()
        panel.setLayout(side)
        panel.setMinimumWidth(300)

        self.view = ImageView()
        split = QSplitter()
        split.addWidget(panel)
        split.addWidget(self.view)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)
        self.resize(1400, 860)
        self.load(config_path)

    # --- config -----------------------------------------------------------------------------

    def load(self, path):
        self.path = Path(path).resolve()
        self.text = self.path.read_text(encoding="utf-8")
        self.original = self.text
        self.setWindowTitle(f"DesignRenders — {self.path.name}")
        self.file_label.setText(self.path.relative_to(ROOT).as_posix() if self.path.is_relative_to(ROOT)
                                else str(self.path))
        self._fill_palette()
        cfg = json.loads(self.text)
        self.camera.blockSignals(True)
        self.camera.clear()
        self.camera.addItems([c["name"] for c in cfg.get("cameras", [])])
        self.camera.blockSignals(False)
        self.changed()

    def _fill_palette(self):
        while self.palette_form.rowCount():
            self.palette_form.removeRow(0)
        cfg = json.loads(self.text)
        for name, value in cfg.get("palette", {}).items():
            if not HEX.fullmatch(value):
                continue
            button = QPushButton()
            button.clicked.connect(lambda _=False, n=name, b=button: self.pick(n, b))
            self._paint(button, value)
            label = QLabel(f"<b>{name}</b><br><span style='color:gray'>{color_usage(cfg, name)}</span>")
            label.setWordWrap(True)
            self.palette_form.addRow(label, button)

    @staticmethod
    def _paint(button, value):
        c = QColor(value)
        ink = "#000" if (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) > 140 else "#fff"
        button.setText(value.upper())
        button.setMinimumWidth(110)
        button.setStyleSheet(f"background:{value}; color:{ink}; padding:6px; border:1px solid #888;")

    def pick(self, name, button):
        color = QColorDialog.getColor(QColor(button.text()), self, f"Цвет «{name}»")
        if not color.isValid():
            return
        value = color.name().upper()
        self.text = set_palette_color(self.text, name, value)
        self.path.write_text(self.text, encoding="utf-8")
        self._paint(button, value)
        self.changed()

    def revert(self):
        self.text = self.original
        self.path.write_text(self.text, encoding="utf-8")
        self._fill_palette()
        self.changed()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Конфиг комнаты", str(ROOT / "rooms"), "JSON (*.json)")
        if path:
            self.load(path)

    # --- rendering --------------------------------------------------------------------------

    def changed(self, *_):
        if self.auto.isChecked():
            self.debounce.start()

    def render(self):
        if self.proc is not None:
            self.pending = True  # render again with the latest settings when this one ends
            return
        args = [str(ROOT / "render.py"), str(self.path), "--camera", self.camera.currentText(),
                "--clay" if self.clay.isChecked() else "--no-clay"]
        args += [["--preview"], [], ["--final"]][self.quality.currentIndex()]
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(ROOT))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.finished.connect(self._done)
        self.proc.start(str(PYTHON), args)
        self.clock.start()
        self.ticker.start()
        self._tick()

    def _tick(self):
        self.status.setText(f"Рендер «{self.camera.currentText()}»… {self.clock.elapsed() / 1000:.1f} с")

    def _done(self, code, _status):
        self.ticker.stop()
        out = bytes(self.proc.readAll()).decode(errors="replace")
        self.proc.deleteLater()
        self.proc = None
        hits = RENDERED.findall(out)
        if code == 0 and hits:
            self.view.show_image(hits[-1][1])
            self.status.setText(f"Готово за {self.clock.elapsed() / 1000:.1f} с (Blender: {hits[-1][0]} с)")
        else:
            tail = "\n".join(line for line in out.splitlines() if not line.startswith("Fra:"))[-1500:]
            self.status.setText(f"Ошибка рендера:\n{tail}")
        if self.pending:
            self.pending = False
            self.render()


def main():
    app = QApplication(sys.argv)
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "rooms" / "apartment.json"
    win = Editor(path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
