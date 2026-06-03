async def run(objective, plan, mcp, log):
    log("drafting paper outline")
    title = objective.strip().capitalize()
    return f"""# {title}

## Thesis
TBD, but make it sharp.

## Outline
1. Context
2. Main argument
3. Evidence
4. Counterpoint
5. Conclusion

## Plan Notes
{plan}
"""
