import sys
import asyncio
import importlib.util
from client import mcp, log

async def main():
    try:
        code = sys.stdin.read()
        spec = importlib.util.spec_from_loader('skill', loader=None)
        skill = importlib.util.module_from_spec(spec)
        exec(code, skill.__dict__)

        objective = sys.argv[1]
        plan = sys.argv[2]

        result = await skill.run(objective, plan, mcp, log)
        print(f"\n---RESULT---\n{result}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
