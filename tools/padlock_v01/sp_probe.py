import json
import sys
import substance_painter.project as P
import substance_painter.application as A
print(json.dumps({"open":P.is_open(),"file":P.file_path() if P.is_open() else None,"python":sys.version,"application_api":[n for n in dir(A) if 'version' in n.lower()]},ensure_ascii=False))
