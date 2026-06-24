from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

report = Path("report.txt").read_text(encoding="utf-8")

readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")

start = "<!-- FIRE_REPORT_START -->"
end = "<!-- FIRE_REPORT_END -->"

now = datetime.now(ZoneInfo("Asia/Taipei"))

block = f"""<!-- FIRE_REPORT_START -->
## 今日火鳳雷達

更新時間：{now.strftime("%Y-%m-%d %H:%M")} 台灣時間

```text
{report.strip()}
```
<!-- FIRE_REPORT_END -->"""

if start in readme and end in readme:
    before = readme.split(start)[0]
    after = readme.split(end)[1]
    readme = before + block + after
else:
    readme = block + "\n\n---\n\n" + readme

readme_path.write_text(readme, encoding="utf-8")
