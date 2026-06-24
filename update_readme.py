from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

README_PATH = Path("README.md")
REPORT_PATH = Path("report.txt")

START = "<!-- FIRE_REPORT_START -->"
END = "<!-- FIRE_REPORT_END -->"


def read_report():
    if not REPORT_PATH.exists():
        return "火鳳雷達執行失敗：找不到 report.txt，請查看 GitHub Actions log。"

    report = REPORT_PATH.read_text(encoding="utf-8", errors="replace").strip()

    if not report:
        return "火鳳雷達執行失敗：report.txt 是空的，請查看 GitHub Actions 的 Run Fire Phoenix 步驟。"

    return report


def read_readme():
    if not README_PATH.exists():
        return "# FirePhoenixRadar 🔥🦅\n"

    return README_PATH.read_text(encoding="utf-8", errors="replace")


def build_block(report):
    now = datetime.now(ZoneInfo("Asia/Taipei"))

    return f"""<!-- FIRE_REPORT_START -->
## 今日火鳳雷達

更新時間：{now.strftime("%Y-%m-%d %H:%M")} 台灣時間

```text
{report}
```
<!-- FIRE_REPORT_END -->"""


def update_readme(readme, block):
    if START in readme and END in readme:
        before = readme.split(START)[0]
        after = readme.split(END)[1]
        return before + block + after

    return block + "\n\n---\n\n" + readme


def main():
    report = read_report()
    readme = read_readme()
    block = build_block(report)
    updated = update_readme(readme, block)

    README_PATH.write_text(updated, encoding="utf-8")

    print("README updated.")
    print()
    print(report)


if __name__ == "__main__":
    main()
