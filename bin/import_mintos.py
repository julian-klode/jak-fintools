#!/usr/bin/python3
#
# Copyright (C) 2019 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Importer for mintos emails.

This imports interest from daily mintos notification emails stored in a
notmuch maildir. It only works for German mintos email."""
import argparse
import datetime
import decimal
import email
import email.policy
import os
import pickle
import sys
import typing
from contextlib import contextmanager

import bs4  # type: ignore

try:
    import notmuch  # type: ignore

    _nm_exc = None  # pylint: disable=invalid-name
except ImportError as nm_exc:
    _nm_exc = nm_exc  # pylint: disable=invalid-name
    notmuch = None

CACHE_PATH = os.path.expanduser("~/.cache/mintos.pickle")
CACHE_VERSION = 1
CacheType = typing.Dict[str, typing.Tuple[datetime.date, decimal.Decimal]]


def iter_email_paths(args: typing.List[str]) -> typing.Iterator[str]:
    """Iterate over paths of matching emails."""
    if len(args) > 0:
        yield from args
        return
    if notmuch is None:
        print(
            f"E: No files specified on command-line and could not import notmuch: {_nm_exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    database = notmuch.Database()
    query = notmuch.Query(
        database, "from:mintos subject:tägliche subject:Zusammenfassung"
    )
    query.set_sort(notmuch.Query.SORT.OLDEST_FIRST)  # pylint: disable=no-member
    msgs = query.search_messages()
    for msg in msgs:
        yield msg.get_filename()


def read_email(path: str) -> typing.Tuple[datetime.date, decimal.Decimal]:
    """Read the email, return a (date, value) tuple"""
    with open(path, encoding="utf-8") as fobj:
        msg = email.message_from_file(fobj, policy=email.policy.default)

    body: str = msg.get_body().get_content()  # type: ignore
    soup = bs4.BeautifulSoup(body, features="lxml")
    table = soup.select(
        ':has(:-soup-contains-own("€")):has(:-soup-contains-own("Gesamtertrag"))'
    )[-1]
    try:
        value = decimal.Decimal(
            table.select(':-soup-contains-own("€"):not(:-soup-contains-own("Bonus"))')[
                -1
            ]
            .text.strip("€")
            .strip()
        )
    except IndexError:
        value = decimal.Decimal(
            soup.select(':-soup-contains-own("€")')[-1].text.strip("€").strip()
        )
    date = datetime.datetime.strptime(
        soup.select(':-soup-contains-own("Endsaldo")')[-1]
        .text.replace("Endsaldo", "")
        .strip(),
        "%d.%m.%Y",
    ).date()

    return (date, value)


@contextmanager
def open_atomic_write(path: str) -> typing.Iterator[typing.BinaryIO]:
    """Open file atomically as .new, then rename after write"""
    try:
        with open(path + ".new", "wb") as fobj:
            yield fobj
    except Exception as exc:
        os.unlink(path + ".new")
        raise exc
    else:
        os.rename(path + ".new", path)


@contextmanager
def open_cache() -> typing.Iterator[CacheType]:
    """Context manager for a cache, loads it on enter, stores on exit."""
    cache: CacheType = {}

    try:
        with open(CACHE_PATH, "rb") as cachef:
            wrapped_cache: typing.Dict[str, typing.Union[int, CacheType]] = pickle.load(
                cachef
            )
    except FileNotFoundError:
        pass
    else:
        if wrapped_cache.get("version") == CACHE_VERSION:
            cache = typing.cast(CacheType, wrapped_cache["cache"])

    yield cache

    with open_atomic_write(CACHE_PATH) as cachef:
        try:
            pickle.dump({"version": CACHE_VERSION, "cache": cache}, cachef)
        except Exception as exc:  # pylint: disable=broad-except
            print(exc, file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """Output a CSV for portfolio performance based on mintos daily emails."""
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "emails", metavar="E", type=str, nargs="*", help="emails to import"
    )
    parser.add_argument(
        "-f",
        dest="format",
        choices=["ledger", "csv"],
        default="csv",
        help="output format",
    )

    args = parser.parse_args()

    with open_cache() as cache:
        if args.format == "csv":
            print("Datum;Wert;Typ")

        acc = decimal.Decimal(0)
        for path in iter_email_paths(args.emails):
            try:
                date, value = cache[path]
            except KeyError:
                date, value = read_email(path)
                cache[path] = (date, value)

            if value - acc == 0:
                continue
            if args.format == "csv":
                if value - acc < 0:
                    print(
                        "{};{};Zinsbelastung".format(
                            date, str(acc - value).replace(".", ",")
                        )
                    )
                else:
                    print(
                        "{};{};Zinsen".format(date, str(value - acc).replace(".", ","))
                    )
            elif args.format == "ledger":
                print("{} Mintos Zinsen".format(date.strftime("%Y/%m/%d")))
                increment = value - acc
                print(f"    income:bank:mintos  {-increment}€")
                print(f"    assets:bank:savings:mintos  {increment}€")
                print()
            acc = value


if __name__ == "__main__":
    main()
