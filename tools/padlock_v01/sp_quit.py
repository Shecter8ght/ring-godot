"""Quit only the isolated, empty Painter instance controlled by this queue."""
from PySide6.QtCore import QTimer
import substance_painter.project as P
import substance_painter.application as A
if P.is_open():raise RuntimeError('Refusing to quit with an open project')
QTimer.singleShot(1000,A.close)
print('EMPTY_PADLOCK_PAINTER_WILL_CLOSE')
