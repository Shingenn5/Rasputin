from collections import defaultdict
from pathlib import Path

GROUPS = {
    "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"},
    "spreadsheets": {".xls", ".xlsx", ".csv", ".tsv"},
    "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
    "code": {".py", ".js", ".html", ".css", ".json", ".yml", ".yaml", ".toml"},
    "archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
}


def bucket(name):
    suffix = Path(name).suffix.lower()
    for group, exts in GROUPS.items():
        if suffix in exts:
            return group
    return "misc"


async def run(objective, plan, mcp, log):
    log("scanning folder")
    listing = await mcp.call_tool("fs_list", {"path": "."})
    moves = []
    grouped = defaultdict(list)
    for item in listing.get("items", []):
        if item["kind"] != "file":
            continue
        group = bucket(item["name"])
        grouped[group].append(item["name"])
        moves.append((item["name"], f"{group}/{item['name']}"))

    lines = ["Folder organization plan:", ""]
    for group, names in grouped.items():
        lines.append(f"{group}:")
        for name in names[:25]:
            lines.append(f"- {name}")

    # only moves if permission is enabled
    moved = []
    for src, dst in moves:
        try:
            await mcp.call_tool("fs_mkdir", {"path": str(Path(dst).parent)})
            await mcp.call_tool("fs_move", {"source": src, "target": dst})
            moved.append(f"{src} -> {dst}")
        except PermissionError:
            lines.append("")
            lines.append("Reorganize permission is off, so this is a plan only.")
            break
        except Exception as exc:
            moved.append(f"skip {src}: {exc}")

    if moved:
        lines.append("")
        lines.append("Moved:")
        lines.extend(f"- {x}" for x in moved)
    return "\n".join(lines)
