#!/usr/bin/python3
#
# Copyright (C) 2019 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Stupid robo advisor."""
import argparse
import itertools
import math
import subprocess
import typing

from tabulate import tabulate


# pylint: disable=inherit-non-class,too-few-public-methods
class Position(typing.NamedTuple):
    """A position in the portfolio."""

    min: int
    tgt: int
    max: int


TARGET = {
    "world": Position(72, 80, 100),
    "em imi": Position(8, 10, 12),
    "world sc": Position(8, 10, 12),
}

POSITIONS_BY_ISIN = {
    "IE00B4L5Y983": "world",
    "IE00BF4RFH31": "em imi",
    "IE00BKM4GZ66": "world sc",
}


# We do not want to make purchases just purely on optimal results but
# also with some more predictability. Optimally we purchase satellites
# at the same time or we purchase the core, but we don't want to buy
# just one satellite or change core and a satellite at the same time
# if we do not have to.
CLUSTERS = {"world", "em imi, world sc"}

Allocation = typing.NewType("Allocation", typing.Dict[str, float])


def validity_score(allocation: Allocation) -> int:
    """Check if an allocation is valid.

    An allocation is considered valid if each of its positions is within its
    specified range.

    :returns: the number of limits violated.
    """
    total = sum(allocation.values())
    diff = 0
    for name, value in allocation.items():
        position = TARGET[name]
        percentage = value / total * 100
        diff += int(percentage > position.max)
        diff += int(percentage < position.min)

    return diff


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


def get_starting_point() -> Allocation:
    """Return the starting allocation, queried from hledger."""
    print("Gathering data", end="", flush=True)
    res = Allocation({})

    for isin, name in POSITIONS_BY_ISIN.items():
        print(".", end="", flush=True)
        value_output = int(
            float(
                subprocess.getoutput(f"hledger bal -V cur:{isin}")
                .splitlines()[-1]
                .strip()
                .split()[0]
                .rstrip("€")
                .replace(",", "")
            )
        )

        try:
            res[name] += value_output
        except KeyError:
            res[name] = value_output

    print("\r", end="")
    return res


def main() -> None:
    """Entry point."""

    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("--rounds", dest="rounds", type=int, default=12)
    parser.add_argument("invest", type=int)
    parser.add_argument("--min", dest="min", type=int, default=1)
    parser.add_argument("--max", dest="max", type=int, default=len(POSITIONS_BY_ISIN))
    args = parser.parse_args()

    values = get_starting_point()
    etfs = set(TARGET.keys())
    rows: typing.List[typing.Iterable[object]] = [
        ["iteration", "buy"]
        + sorted(TARGET, key=lambda k: TARGET[k].tgt, reverse=True),
        ["start", "-"]
        + [
            "{} ({:.2f}%)".format(
                values.get(k, "-"), values.get(k, 0) / sum(values.values()) * 100
            )
            for k in sorted(TARGET, key=lambda k: TARGET[k].tgt, reverse=True)
        ],
    ]

    for i in range(args.rounds):
        choices: typing.List[typing.Tuple[str, Allocation]] = []
        for this_num_trans in range(args.min, args.max + 1):
            choices += [
                (", ".join(etfs), buy(values, etfs, args.invest))
                for etfs in itertools.combinations(sorted(etfs), this_num_trans)
            ]
        choice_buy, choice = min(
            choices,
            key=lambda choice: (
                validity_score(choice[1]),
                choice[0] not in CLUSTERS,
                choice[0].count(","),
                calculate_distance(choice[1]),
            ),
        )

        if validity_score(choice) != 0:
            print("ERROR: Cannot proceed at iteration {}, no valid choices", i)

        if values == choice:
            print("ERROR")
            break
        total = sum(choice.values())
        row = [i + 1, choice_buy] + [
            "{} ({:.2f}%)".format(choice.get(k, "-"), choice.get(k, 0) / total * 100)
            for k in sorted(TARGET, key=lambda k: TARGET[k].tgt, reverse=True)
        ]
        rows.append(row)
        values = choice

    print(tabulate(rows, headers="firstrow"))


if __name__ == "__main__":
    main()
