"""Dataset management for Trials."""

from . import store


SEED_DATASETS = [
    {
        "name": "Basic Reasoning",
        "type": "questions",
        "entries": [
            {"prompt": "What is 2 + 2? Explain your reasoning step by step.", "expected": "4"},
            {"prompt": "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly?", "expected": "No, we cannot conclude this."},
            {"prompt": "A farmer has 17 sheep. All but 9 die. How many sheep are left?", "expected": "9"},
            {"prompt": "What comes next in the sequence: 2, 6, 12, 20, 30, ?", "expected": "42"},
            {"prompt": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?", "expected": "5 minutes"},
        ],
        "tags": ["reasoning", "math", "logic", "seed"],
    },
    {
        "name": "Coding Tasks",
        "type": "tasks",
        "entries": [
            {"prompt": "Write a Python function that reverses a string without using built-in reverse methods.", "expected_contains": "def"},
            {"prompt": "Explain the difference between a stack and a queue.", "expected_contains": "FIFO"},
            {"prompt": "Write a SQL query to find the second highest salary from an employees table.", "expected_contains": "SELECT"},
            {"prompt": "What is the time complexity of binary search?", "expected": "O(log n)"},
            {"prompt": "Write a function to check if a string is a palindrome.", "expected_contains": "def"},
        ],
        "tags": ["coding", "programming", "seed"],
    },
    {
        "name": "Instruction Following",
        "type": "evaluation",
        "entries": [
            {"prompt": "List exactly 5 colors of the rainbow, one per line.", "criteria": "Exactly 5 lines, each a rainbow color"},
            {"prompt": "Respond with only the word 'yes' or 'no': Is the sky blue?", "criteria": "Response is exactly 'yes' or 'no'"},
            {"prompt": "Write a haiku about technology.", "criteria": "5-7-5 syllable structure"},
            {"prompt": "Summarize the concept of gravity in exactly one sentence.", "criteria": "Single sentence, covers key concept"},
            {"prompt": "Translate 'hello world' to French, Spanish, and German. Format as a bullet list.", "criteria": "Three items in bullet list format"},
        ],
        "tags": ["instruction-following", "format", "seed"],
    },
]


def seed_datasets():
    """Create seed datasets if none exist yet."""
    existing = store.list_datasets()
    if existing:
        return existing
    created = []
    for ds_data in SEED_DATASETS:
        ds = store.create_dataset(
            name=ds_data["name"],
            ds_type=ds_data["type"],
            entries=ds_data["entries"],
            tags=ds_data.get("tags", []),
        )
        created.append(ds)
    return created
