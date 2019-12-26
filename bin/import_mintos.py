#!/usr/bin/python3
#
# Copyright (C) 2019 Julian Andres Klode
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Importer for mintos emails.

This imports interest from daily mintos notification emails stored in a
notmuch maildir. It only works for German mintos email."""
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
except ImportError as exc:
    _nm_exc = exc  # pylint: disable=invalid-name
    notmuch = None

CACHE_PATH = os.path.expanduser("~/.cache/mintos.pickle")
CACHE_VERSION = 1
CacheType = typing.Dict[str, typing.Tuple[datetime.date, decimal.Decimal]]


def iter_email_paths() -> typing.Iterator[str]:
    """Iterate over paths of matching emails."""
    if len(sys.argv) > 0:
        yield from sys.argv[1:]
    if notmuch is None:
        print(
            f"E: No files specified on command-line and could not import notmuch: {_nm_exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    database = notmuch.Database()
    query = notmuch.Query(database, "from:mintos tägliche")
    query.set_sort(notmuch.Query.SORT.OLDEST_FIRST)  # pylint: disable=no-member
    msgs = query.search_messages()
    for msg in msgs:
        yield msg.get_filename()


def read_email(path: str) -> typing.Tuple[datetime.date, decimal.Decimal]:
    """Read the email, return a (date, value) tuple"""
    with open(path) as fobj:
        msg = email.message_from_file(fobj, policy=email.policy.default)
    body: str = msg.get_content()  # type: ignore

    soup = bs4.BeautifulSoup(body, features="lxml")
    table = soup.select('table:contains("Gesamtertrag")')[-1]
    value = decimal.Decimal(table.select(':contains("€")')[-1].text.strip("€").strip())
    date = datetime.datetime.strptime(
        soup.select('td:contains("Endsaldo")')[-1].text.replace("Endsaldo", "").strip(),
        "%d.%m.%Y",
    ).date()

    return (date, value)


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

    with open(CACHE_PATH, "wb") as cachef:
        try:
            pickle.dump({"version": CACHE_VERSION, "cache": cache}, cachef)
        except Exception as exc:  # pylint: disable=broad-except
            print(exc, file=sys.stderr)
            os.unlink(CACHE_PATH)
            sys.exit(1)


def main() -> None:
    """Output a CSV for portfolio performance based on mintos daily emails."""
    with open_cache() as cache:
        print("Datum;Wert;Typ")

        acc = decimal.Decimal(0)
        for path in iter_email_paths():
            try:
                date, value = cache[path]
            except KeyError:
                date, value = read_email(path)
                cache[path] = (date, value)
            print("{};{};Zinsen".format(date, str(value - acc).replace(".", ",")))
            acc = value


if __name__ == "__main__":
    main()
