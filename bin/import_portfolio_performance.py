#!/usr/bin/env python3
#
# Copyright (C) 2020 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Import price information from portfolio performance."""

import decimal
import sys
import xml.etree.ElementTree as ET


def parse_pp(path: str) -> None:
    """Parse the given portfolio performance xml file"""

    tree = ET.parse(path)
    root = tree.getroot()
    securities = root.find("securities")

    assert securities is not None

    for security in securities:
        isin_el = security.find("isin")
        if isin_el is None:
            continue

        isin = isin_el.text

        prices = security.find("prices")
        assert prices is not None
        for price in prices:
            date = price.attrib["t"].replace("-", "/")
            value = decimal.Decimal(price.attrib["v"]) / 10000 / 10000

            print(f'P {date} "{isin}" {value}€')


if __name__ == "__main__":
    parse_pp(sys.argv[1])
