import os

def bundle_code():
    output_file = "repro-output.md"
    # Folders to ignore
    ignore_dirs = [".git", "__pycache__", ".venv", "node_modules", ".codex", "data"]
    # Files to ignore
    ignore_files = [output_file, ".gitignore", "requirements.txt", "*.pyc", "*.exe"]

    with open(output_file, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk("."):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file in files:
                if file in ignore_files or file.endswith(".pyc") or file.endswith(".exe"):
                    continue

                filepath = os.path.join(root, file)

                # Write a header for each file
                outfile.write(f"\n\n{'='*50}\n")
                outfile.write(f"FILE: {filepath}\n")
                outfile.write(f"{'='*50}\n\n")

                try:
                    with open(filepath, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"ERROR_READING_FILE: {e}")

if __name__ == "__main__":
    bundle_code()
    print("Success! Created 'repro-output.md'. Please upload this file.")