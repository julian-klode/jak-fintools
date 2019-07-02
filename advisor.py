import math
from tabulate import tabulate
import collections


Position = collections.namedtuple('Position', ['min', 'tgt', 'max'])


target = {
    "world": Position(70, 77, 100),
    "em imi": Position(0, 10, 15),
    "world sc": Position(0, 13, 15),
}


def is_valid(allocation):
    """Check if an allocation is valid.

    An allocation is considered valid if each of its positions is within its
    specified range.
    """
    total = sum(allocation.values())
    for name, value in allocation.items():
        position = target[name]
        percentage = value / total * 100
        if percentage > position.max or percentage < position.min:
            return False
    return True


def calculate_distance(allocation):
    """Calculate score of a given allocation.

    The score of a given allocation is the euclidean distance between
    the specified allocation and the target allocation. The lower the
    score, the better."""
    total = sum(allocation.values())
    diffs = (target[k].tgt - allocation.get(k, 0) /
             total * 100 for k in target)
    return math.sqrt(sum(diff**2 for diff in diffs))


def buy(values, etf, value):
    """Buy the given ETF for the given value.

    Returns a new allocation."""
    new_values = dict(values)
    try:
        new_values[etf] += value
    except KeyError:
        new_values[etf] = value
    return new_values


def main():
    value = 0
    invest = 1000
    rounds = 100

    values = {}
    etfs = set(target.keys())
    rows = [["iteration", "buy"] +
            [k for k in sorted(target, key=lambda k: target[k].tgt, reverse=True)]]

    for i in range(rounds):
        choices = [(etf, buy(values, etf, invest)) for etf in sorted(etfs)]
        choice_buy, choice = min(choices, key=lambda choice: (
            not is_valid(choice[1]), calculate_distance(choice[1])))

        if not is_valid(choice):
            print("ERROR: Cannot proceed at iteration {}, no valid choices", i)

        if values == choice:
            print("ERROR")
            break
        total = sum(choice.values())
        row = [i + 1, choice_buy] + ["%s (%.2f%%)" % (choice.get(k, "-"), choice.get(
            k, 0) / total * 100) for k in sorted(target, key=lambda k: target[k], reverse=True)]
        rows.append(row)
        values = choice

    print(tabulate(rows, headers="firstrow"))


if __name__ == '__main__':
    main()
