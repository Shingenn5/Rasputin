async def run(objective, plan, mcp, log):
    log("searching web")
    search = await mcp.call_tool("web_search", {"query": objective, "max_results": 5})
    lines = [f"Research task: {objective}", "", "Plan:", plan, "", "Search hits:"]
    for item in search.get("results", []):
        lines.append(f"- {item.get('title', 'untitled')}")
    if search.get("error"):
        lines.append(f"Search error: {search['error']}")
    return "\n".join(lines)
