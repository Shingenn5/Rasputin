"""Operator CLI for resetting the Rasputin admin password without hand-editing
the database. Run as:

    python -m backend.tools.reset_password [--username NAME]

The new password is always generated server-side (never accepted as a CLI
argument) so it never shows up in shell history or the process list.
"""

import argparse
import sys

from backend.core import auth as auth


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m backend.tools.reset_password",
        description="Reset a Rasputin user's password and print the new credentials.",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="user to reset (defaults to the first admin-role user)",
    )
    args = parser.parse_args(argv)

    try:
        result = auth.reset_password(username=args.username)
    except Exception as exc:
        print(f"Password reset failed: {exc}", file=sys.stderr)
        return 1

    print("")
    print("Rasputin admin credentials (reset)")
    print(f"  username: {result['username']}")
    print(f"  password: {result['password']}")
    print("Change this after first login if you expose the app beyond localhost.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
