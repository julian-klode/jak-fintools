#!/usr/bin/python3
"""Stupid robo advisor."""
import itertools
import math
import typing

from tabulate import tabulate


class Position(typing.NamedTuple):
    """A position in the portfolio."""

    min: int
    tgt: int
    max: int


TARGET = {
    "world": Position(70, 77, 100),
    "em imi": Position(0, 10, 15),
    "world sc": Position(0, 13, 15),
}

Allocation = typing.NewType("Allocation", typing.Dict[str, float])


def is_valid(allocation: Allocation) -> bool:
    """Check if an allocation is valid.

    An allocation is considered valid if each of its positions is within its
    specified range.
    """
    total = sum(allocation.values())
    for name, value in allocation.items():
        position = TARGET[name]
        percentage = value / total * 100
        if percentage > position.max or percentage < position.min:
            return False
    return True


def calculate_distance(allocation: Allocation) -> float:
    """Calculate score of a given allocation.

    The score of a given allocation is the euclidean distance between
    the specified allocation and the TARGET allocation. The lower the
    score, the better."""
    total = sum(allocation.values())
    diffs = (TARGET[k].tgt - allocation.get(k, 0) / total * 100 for k in TARGET)
    return math.sqrt(sum(diff ** 2 for diff in diffs))


def buy(values: Allocation, etfs: typing.Iterable[str], value: float) -> Allocation:
    """Buy the given ETFs for the given value.

    Returns a new allocation. The new allocation will have an overall
    value of the of allocation + the value to be allocated."""
    total = sum(values.values()) + value
    fixed = sum(values[k] for k in values if k not in etfs)
    free = total - fixed

    # The optimal allocation given the entire asset value
    optimum = {k: TARGET[k].tgt / 100 * total for k in TARGET}
    # Amount to multiply TARGET allocation with to get the same relative
    # allocation for the given etfs from the free money.
    optimum_multiplier = free / sum(optimum[k] for k in etfs)

    new_values = Allocation(values.copy())
    for etf in etfs:
        # Calculate the value for this ETF, and clamp it to within its limits
        val = optimum[etf] * optimum_multiplier
        val = min(val, TARGET[etf].max * total / 100)
        val = max(val, TARGET[etf].min * total / 100)
        val = int(val)
        new_values[etf] = val
        free -= val

    # Something was incomplete, let's add the remainder of the free amount to
    # the largest free position.
    if free:
        new_values[max(etfs, key=lambda k: TARGET[k].tgt)] += free

    return new_values


def main() -> None:
    """Entry point."""
    invest = 1000
    rounds = 100
    num_transactions = 1

    values = Allocation({})
    etfs = set(TARGET.keys())
    rows: typing.List[typing.Iterable[object]] = [
        ["iteration", "buy"]
        + [k for k in sorted(TARGET, key=lambda k: TARGET[k].tgt, reverse=True)]
    ]

    for i in range(rounds):
        choices = [
            (", ".join(etfs), buy(values, etfs, invest))
            for etfs in itertools.combinations(sorted(etfs), num_transactions)
        ]
        choice_buy, choice = min(
            choices,
            key=lambda choice: (not is_valid(choice[1]), calculate_distance(choice[1])),
        )

        if not is_valid(choice):
            print("ERROR: Cannot proceed at iteration {}, no valid choices", i)

        if values == choice:
            print("ERROR")
            break
        total = sum(choice.values())
        row = [i + 1, choice_buy] + [
            "%s (%.2f%%)" % (choice.get(k, "-"), choice.get(k, 0) / total * 100)
            for k in sorted(TARGET, key=lambda k: TARGET[k], reverse=True)
        ]
        rows.append(row)
        values = choice

    print(tabulate(rows, headers="firstrow"))


if __name__ == "__main__":
    main()
