from pathlib import Path
from datetime import datetime

report = Path("report.txt").read_text(encoding="utf-8")

readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")

start = "<!-- FIRE_REPORT_START -->"
end = "<!-- FIRE_REPORT_END -->"

block = f"""<!-- FIRE_REPORT_START -->
## 今日火鳳雷達

更新時間：{datetime.now().strftime("%Y-%m-%d %H:%M")}

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