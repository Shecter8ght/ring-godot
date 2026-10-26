"""Read only diagnostics of this task's isolated Painter window and modal dialogs."""
import json
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

report=[]
for widget in QApplication.topLevelWidgets():
    if widget.windowTitle() or widget.isModal():
        report.append({'class':type(widget).__name__,'name':widget.objectName(),
                       'title':widget.windowTitle(),'visible':widget.isVisible(),
                       'modal':widget.isModal(),
                       'labels':[x.text() for x in widget.findChildren(QLabel)],
                       'buttons':[x.text() for x in widget.findChildren(QPushButton)]})
print(json.dumps(report,ensure_ascii=False))
