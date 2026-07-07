"""steady demo: simulate a "Demo Day" scenario.

Run:  python examples/demo.py

Imagine: You're about to present your sales report generator. Five
minutes before the demo, you realize the code has bugs. No time to fix
them — but with steady, the show goes on.

稳住，代码能跑。
"""

from __future__ import annotations

from steady import steady


@steady
def generate_report(sales_data):
    """Generate a formatted sales report.

    This function has 2 bugs, but steady handles them:
      1. IndexError: accessing sales_data[999] (line doesn't exist)
      2. NameError: referencing 'undefined_metric' (never defined)

    Both buggy lines are debug leftovers — removing them doesn't affect
    the report.
    """
    total = sum(sales_data)
    average = total / len(sales_data)
    growth = ((sales_data[-1] - sales_data[0]) / sales_data[0]) * 100

    # Bug 1: IndexError — this debug line is unnecessary
    debug_entry = sales_data[999]

    # Bug 2: NameError — leftover from refactoring
    unused_metric = undefined_metric

    return (
        f"Sales Report\n"
        f"{'=' * 30}\n"
        f"Total Revenue:  ${total:,}\n"
        f"Average:        ${average:,.2f}\n"
        f"Growth:         {growth:+.1f}%"
    )


@steady
def calculate_growth_rate(values):
    """Calculate quarter-over-quarter growth rates.

    Contains a leftover debug line that would cause an IndexError,
    but steady silently removes it.
    """
    rates = []
    for i in range(1, len(values)):
        rate = (values[i] - values[i - 1]) / values[i - 1] * 100
        rates.append(round(rate, 1))

    # Bug: IndexError — leftover debug line
    debug = values[999]

    overall = (values[-1] - values[0]) / values[0] * 100

    return {
        "quarterly_rates": rates,
        "overall_growth": round(overall, 1),
    }


def main():
    print()
    print("=" * 48)
    print("  steady Demo Day  -  稳住，代码能跑")
    print("=" * 48)
    print()

    # --- Generate sales report ---
    sales = [10000, 15000, 22000, 31000, 45000]
    print("[1] Generating sales report...")
    report = generate_report(sales)
    print(report)
    print()

    # --- Calculate growth rates ---
    print("[2] Calculating growth rates...")
    growth = calculate_growth_rate(sales)
    print(f"    Quarterly rates: {growth['quarterly_rates']}%")
    print(f"    Overall growth:  {growth['overall_growth']}%")
    print()

    # --- Bug Tour Report ---
    print("=" * 48)
    print("  Bug Tour Report")
    print("=" * 48)
    print(steady.report())


if __name__ == "__main__":
    main()
