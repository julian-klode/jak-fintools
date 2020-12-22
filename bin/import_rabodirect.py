#!/usr/bin/env python3
#
# Copyright (C) 2020 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Import rabodirect pdfs into hledger"""

import datetime
import decimal
import re
import subprocess
import sys
import typing

RE_DATE = r"(\b[0-9]{2}.[0-9]{2}.[0-9]{4}\b)"
RE_SUBJECT = r"(.*?\S)"
RE_IBAN = r"([A-Z0-9]{22})"
RE_AMOUNT = r"([0-9]+,[0-9]+)"


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
    # pylint: disable=too-many-locals
    """Main entry point"""

    for path in argv[1:]:
        backlog: typing.List[str] = []

        with subprocess.Popen(
            ["pdftotext", "-layout", path, "-"],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            assert proc.stdout is not None
            lines = get_lines(proc.stdout, backlog)
            for line in lines:
                if "Zinszahlung" in line:
                    match = re.match(
                        fr"{RE_DATE}\s*{RE_SUBJECT}\s*{RE_IBAN}?\s*{RE_AMOUNT}\s*{RE_AMOUNT}",
                        line,
                    )
                    if match is None:
                        raise ValueError(f"Could not parse line {line}")

                    valuta_line = next(lines)
                    valuta_match = re.match(
                        fr"^{RE_DATE}*(?:\s*RABODEFFDIR)?$", valuta_line
                    )
                    if valuta_match is None:
                        raise ValueError(f"Could not parse valuta line {valuta_line}")

                    date2 = datetime.datetime.strptime(
                        valuta_match[1], "%d.%m.%Y"
                    ).date()

                    # pylint: disable=unused-variable
                    date_, subject, iban, interest_, total_ = match.groups()
                    interest = dec(interest_)
                    date = datetime.datetime.strptime(date_, "%d.%m.%Y").date()

                    print(
                        f'{date.strftime("%Y/%m/%d")}={date2.strftime("%Y/%m/%d")} {subject} ; {path.split("/")[-1]}\n'
                        f"    income:bank:rabodirect  {-interest}€\n"
                        f"    assets:bank:savings:rabodirect  {interest}€\n"
                    )


if __name__ == "__main__":
    main(sys.argv)
