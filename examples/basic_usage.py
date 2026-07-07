"""steady basic usage examples.

Run:  python examples/basic_usage.py

These examples show how steady handles runtime errors without crashing.
No API key is needed — AST repair (fuckit.py-style line removal) handles
everything.
"""

from __future__ import annotations

from steady import steady


# ---------------------------------------------------------------------- #
# Example 1: @steady decorator
# ---------------------------------------------------------------------- #
@steady
def calculate_stats(data):
    """Calculate statistics on a list of numbers.

    The line ``debug = data[999]`` would cause an IndexError, but steady
    removes it and the function returns the correct result.
    """
    total = sum(data)
    average = total / len(data)
    debug = data[999]  # Bug: IndexError (data is too short)
    return f"Total: {total}, Average: {average:.2f}"


print("=" * 50)
print("Example 1: @steady decorator")
print("=" * 50)
print(f"Result: {calculate_stats([10, 20, 30, 40, 50])}")
print()


# ---------------------------------------------------------------------- #
# Example 2: with steady: context manager
# ---------------------------------------------------------------------- #
print("=" * 50)
print("Example 2: with steady: context manager")
print("=" * 50)
with steady:
    data = [1, 2, 3]
    result = sum(data) / len(data)
    print(f"Average: {result}")

# Even if something goes wrong, steady keeps things running
with steady:
    bad_value = 1 / 0  # This would normally crash!
    print("This line won't execute, but the program continues.")
print("Program didn't crash!\n")


# ---------------------------------------------------------------------- #
# Example 3: Bug Tour Report
# ---------------------------------------------------------------------- #
print("=" * 50)
print("Example 3: Bug Tour Report")
print("=" * 50)
print(steady.report())


# ---------------------------------------------------------------------- #
# Example 4: AI-powered repair (requires API key)
# ---------------------------------------------------------------------- #
print("=" * 50)
print("Example 4: AI-powered repair (optional)")
print("=" * 50)
print("""
To enable AI-powered repair:

  # Option 1: Environment variable
  export STEADY_API_KEY="your-key"
  # or falls back to:
  export OPENAI_API_KEY="your-key"

  # Option 2: Programmatic configuration
  steady.configure(api_key="your-key", model="gpt-4o")

  # Option 3: Using python-dotenv (install separately)
  #   pip install python-dotenv
  # Then in your code:
  #   from dotenv import load_dotenv
  #   load_dotenv()  # loads .env file into os.environ
  #   from steady import steady   # steady reads STEADY_API_KEY from os.environ

Without an API key, steady still works — it uses AST repair only.
""")
