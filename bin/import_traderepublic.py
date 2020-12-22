#!/usr/bin/env python3
#
# Copyright (C) 2020 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Import trade republic pdfs into hledger"""

import datetime
import decimal
import re
import subprocess
import sys
import typing


def dec(text: str) -> decimal.Decimal:
    """Convert given text price to decimal"""
    try:
        return decimal.Decimal(
            text.replace(".", "§").replace(",", ".").replace("§", "")
        )
    except Exception as error:
        raise ValueError(
            "Cannot handle input {} -> {}".format(
                text, text.replace(".", "§").replace(",", ".").replace("§", ",")
            )
        ) from error


def get_lines(
    stdout: typing.Iterator[str], backlog: typing.List[str]
) -> typing.Iterator[str]:
    """Iterator over all lines in the output."""
    for line in stdout:
        line = line.strip()

        if not line:
            continue

        yield line
        backlog.append(line)


def main(argv: typing.List[str]) -> None:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Main entry point"""

    for path in argv[1:]:
        count = None
        price = None
        costs = None
        total = None
        total_with_costs = None
        date = None
        isin = None
        taxes = decimal.Decimal(0)
        typ = None

        backlog: typing.List[str] = []

        with subprocess.Popen(
            ["pdftotext", path, "-"], stdout=subprocess.PIPE, encoding="utf-8"
        ) as proc:
            assert proc.stdout is not None
            lines = get_lines(proc.stdout, backlog)
            for line in lines:
                if not typ:
                    for word in (
                        "WERTPAPIERABRECHNUNG",
                        "KONTOAUSZUG",
                        "DEPOTAUSZUG",
                        "STEUERABRECHNUNG",
                    ):
                        if word in line:
                            typ = word
                            break

                if re.match("[0-9]{2}.[0-9]{2}.[0-9]{4}", line) and not date:
                    date = datetime.datetime.strptime(line, "%d.%m.%Y")
                elif line.startswith("ISIN:") or re.match("^[A-Z0-9]{12}$", line):
                    isin = line.split()[-1]
                elif line.endswith("Stk."):
                    count = int(line.split()[0])
                    price = dec(next(lines).strip().split()[0])
                elif line == "Fremdkostenzuschlag":
                    costs = dec(next(lines).strip().split()[0])
                elif line in (
                    "Kapitalertragssteuer",
                    "Kapitalertragsteuer",
                    "Solidaritätszuschlag",
                ):
                    taxes += dec(next(lines).strip().split()[0])
                elif line in (
                    "Kapitalertragsteuer Optimierung",
                    "Solidaritätszuschlag Optimierung",
                ):
                    taxes -= dec(next(lines).strip().split()[0])
                elif line == "GESAMT" and not total:
                    total = dec(next(lines).strip().split()[0])
                elif line == "GESAMT" and total:
                    total_with_costs = dec(next(lines).strip().split()[0])

        if typ == "STEUERABRECHNUNG":
            assert taxes
            assert total
            assert date
            assert not count
            assert not price
            assert not total_with_costs
            assert not isin
            print(
                f'{date.strftime("%Y/%m/%d")} Steueroptimierung  ; {path.split("/")[-1]}'
            )
            print(f"    expenses:taxes                     {taxes}€")
            print(f"    assets:bank:savings:traderepublic  {total}€")
            continue

        assert count
        assert price
        assert costs
        assert total
        assert total_with_costs
        assert date
        assert isin

        print(f'{date.strftime("%Y/%m/%d")} Handel {isin}   ; {path.split("/")[-1]}')
        print(
            f'   assets:bank:savings:traderepublic    {count if total_with_costs < 0 else -count} "{isin}" @ {price}€'
        )

        off = total - count * price
        off = off if total_with_costs < 0 else -off

        print(f"    expenses:bank:traderepublic        {-costs}€")
        if off:
            print(f"    expenses:bank:traderepublic:off    {off}€")
        if taxes:
            print(f"    expenses:taxes                     {-taxes}€")
        print(f"    assets:bank:savings:traderepublic  {total_with_costs}€")


if __name__ == "__main__":
    main(sys.argv)
