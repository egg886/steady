"""Example: using steady with python-dotenv for API key management.

Run:  python examples/with_dotenv.py

steady reads API keys from ``os.environ`` directly. It intentionally does
NOT read ``.env`` files itself — this follows the same convention as the
OpenAI and Anthropic SDKs. The reasoning:

1. **Separation of concerns.** Loading secrets is the application's job,
   not the library's. steady should not impose a dependency on
   ``python-dotenv`` or any specific secrets manager.

2. **No hidden side effects.** Libraries that silently read ``.env`` files
   can cause confusing behaviour in production (e.g. a stray ``.env`` in
   the working directory overriding environment variables). By reading
   only ``os.environ``, steady's behaviour is predictable.

3. **Lazy config.** steady reads ``os.environ`` lazily on first use, so
   any keys you load with ``python-dotenv`` (or ``os.environ["..."] = ...``)
   before the first steady call are automatically picked up.

This example shows the recommended pattern:

    1. Load .env with python-dotenv BEFORE importing steady.
    2. Import steady — it reads the keys from os.environ.

Prerequisites:
    pip install steady[openai]   # or steady[anthropic]
    pip install python-dotenv

Create a .env file in your project root:

    # .env
    STEADY_API_KEY=sk-your-key-here
    # or, reuse an existing OpenAI key:
    # OPENAI_API_KEY=sk-your-openai-key-here

Then run this script.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------- #
# Step 1: Load .env into os.environ FIRST, before importing steady.
# ---------------------------------------------------------------------- #
# python-dotenv reads the .env file and populates os.environ. We do this
# BEFORE importing steady so that steady's lazy config loader sees the keys.
try:
    from dotenv import load_dotenv

    load_dotenv()  # Loads .env from the current directory
    print("[with_dotenv] .env file loaded successfully.")
except ImportError:
    print(
        "[with_dotenv] python-dotenv is not installed.\n"
        "  Install it with:  pip install python-dotenv\n"
        "  Falling back to environment variables only."
    )

# ---------------------------------------------------------------------- #
# Step 2: Import steady — it reads STEADY_API_KEY / OPENAI_API_KEY from
# os.environ on first use.
# ---------------------------------------------------------------------- #
from steady import steady


def main():
    print()
    print("=" * 55)
    print("  steady + python-dotenv Example")
    print("=" * 55)
    print()

    # Check what steady sees.
    from steady import get_config

    config = get_config()
    has_key = bool(config.api_key)
    print(f"  STEADY_API_KEY set : {bool(os.environ.get('STEADY_API_KEY'))}")
    print(f"  OPENAI_API_KEY set : {bool(os.environ.get('OPENAI_API_KEY'))}")
    print(f"  steady sees a key  : {has_key}")
    print(f"  provider           : {config.provider}")
    print(f"  model              : {config.model}")
    print()

    if has_key:
        print("  steady will use LLM repair as a fallback when AST repair")
        print("  cannot fix a bug. The API key is read from os.environ.")
    else:
        print("  No API key found. steady will use AST repair only.")
        print("  This is fine — AST repair works with zero configuration.")
    print()

    # ------------------------------------------------------------------ #
    # Step 3: Use steady as normal. AST repair works without a key.
    # If a key is set, LLM repair kicks in as a fallback.
    # ------------------------------------------------------------------ #
    print("-" * 55)
    print("  Demo: AST repair (works without an API key)")
    print("-" * 55)

    @steady
    def calculate_average(numbers):
        """Calculate the average of a list of numbers.

        Has a debug leftover that causes IndexError, but steady
        removes it via AST repair.
        """
        total = sum(numbers)
        average = total / len(numbers)
        debug = numbers[999]  # Bug: IndexError (debug leftover)
        return average

    result = calculate_average([10, 20, 30, 40, 50])
    print(f"  calculate_average([10, 20, 30, 40, 50]) = {result}")
    print(f"  Bugs intercepted: {steady.bug_count}")
    print()
    print("  The Bug Tour Report records what was repaired:")
    print()
    print(steady.report())

    print("=" * 55)
    print("  Done. steady works with or without an API key.")
    print("=" * 55)


if __name__ == "__main__":
    main()
