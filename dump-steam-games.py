#!/usr/bin/env python3

import argparse
import json
import logging
import requests
import signal
from threading import Event
import time

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from db import Database


class SteamDumper:
    def __init__(self, logger, done_event: Event, debug: bool):
        self.db = Database()
        self.logger = logger
        self.done_event = done_event
        self.debug = debug

        # Timeout for HTTP requests
        self.timeout = 20

        width = Console().width
        self.max_name_width = int(width / 4)

        self.progress = Progress(
            SpinnerColumn(spinner_name="moon"),
            TextColumn(
                "[bold blue]{task.fields[name]:" + str(self.max_name_width) + "}",
                justify="right",
            ),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            MofNCompleteColumn(),
            "•",
            TextColumn('[yellow]{task.fields[sleep]:2.2f}"'),
            "•",
            TimeRemainingColumn(elapsed_when_finished=True),
        )

    def run(self, refresh_list: bool, fetch_missing_details: bool):
        if refresh_list:
            self.refresh_list()

        if fetch_missing_details:
            self.fetch_missing_details()

    # TODO: refactor
    def ellipsise(self, name: str) -> str:
        if len(name) <= self.max_name_width:
            return name

        half = int(self.max_name_width / 2)
        remainder = self.max_name_width % 2

        left = name[: half - (1 - remainder)]
        right = name[-half:]

        return left + "…" + right

    def refresh_list(self):
        url = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/?format=json"
        response = requests.get(url, timeout=self.timeout)
        applist = response.json()

        self.db.connection.execute("BEGIN")
        for app in applist["applist"]["apps"]:
            appid = app["appid"]
            name = app["name"]
            self.db.add_app(appid, name)
        self.db.connection.commit()

    def fetch_missing_details(self):
        sleep_time = 1.2
        penalty = 0.1
        grace = 0.01
        rate_limit_upper_bound_sleep_time = 0

        appids = self.db.list_apps_missing_details()
        app_count = self.db.get_app_count()
        missing_count = len(appids)
        missing_pct = missing_count * 100 / app_count
        self.logger.info(f"Total missing {missing_count}, {missing_pct:.2f}%")
        fetched = 0

        with self.progress:
            task = self.progress.add_task(
                description="",
                total=app_count,
                completed=app_count - missing_count,
                name="Fetch missing details",
                sleep=sleep_time,
            )
            for appid_row in appids:
                if self.done_event.is_set():
                    return

                appid = appid_row["appid"]
                name = appid_row["name"]
                self.progress.update(
                    task,
                    completed=app_count - missing_count + fetched,
                    name=self.ellipsise(name),
                    sleep=sleep_time,
                )
                self.logger.info(f"Fetching details for {name} / {appid}")
                url = f"https://store.steampowered.com/api/appdetails?appids={
                    appid}"
                retry = True
                while retry:
                    retry = False
                    try:
                        response = requests.get(url, timeout=self.timeout)
                    except requests.exceptions.RequestException as e:
                        self.logger.info(f"Exception fetching {url}: {e}")
                        break
                    if response.status_code != 200:
                        self.logger.warn(f"Unexpected server response code {
                            response.status_code}: {response.headers}")
                        if response.status_code == 429:
                            # Rate limited
                            rate_limit_upper_bound_sleep_time = sleep_time
                            sleep_time += penalty
                            self.logger.info(f"Rate limit penalty applied. New sleep time: {
                                sleep_time}")
                            self.progress.update(task, name="Paused…", sleep=sleep_time)
                            time.sleep(120)
                            retry = True
                        else:
                            # Pause and skip, we’ll retry next run anyway
                            self.progress.update(task, name="Paused…")
                            time.sleep(30)
                            break
                else:
                    try:
                        appdetails = response.json()
                        for appid in appdetails:
                            self.db.upsert_app_details(
                                appid, json.dumps(appdetails[appid])
                            )
                    except requests.exceptions.JSONDecodeError as err:
                        self.logger.error(
                            f"JSON decoding error: {str(err)}, content: {response.content}"
                        )

                    fetched += 1
                    self.progress.update(
                        task,
                        completed=app_count - missing_count + fetched,
                        name=self.ellipsise(name),
                        sleep=sleep_time,
                    )
                    if fetched % 100 == 0:
                        sleep_time_tmp = sleep_time - grace
                        if sleep_time_tmp > rate_limit_upper_bound_sleep_time:
                            sleep_time = sleep_time_tmp

                        missing_tmp = missing_count - fetched
                        missing_tmp_pct = missing_tmp * 100 / app_count
                        self.logger.info(f"Total missing {missing_tmp} / {
                            missing_tmp_pct:.2f}%. Sleep time: {sleep_time}")

                    time.sleep(sleep_time)


def handle_sigint(signum, frame):
    done_event.set()


if __name__ == "__main__":
    done_event = Event()
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(
        description="Dumps Steam games to a local database"
    )

    parser.add_argument(
        "--refresh-list",
        help="Whether to fetch the full list of games from Steam",
        type=bool,
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    parser.add_argument(
        "--fetch-missing-details",
        help="Whether to fetch details for apps that are missing them",
        type=bool,
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    parser.add_argument(
        "--debug",
        help="Verbose/debug mode",
        type=bool,
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    args = parser.parse_args()

    verbosity = "INFO"
    console_fmt = "%(message)s"
    show_level = show_path = show_time = False
    if args.debug:
        verbosity = "DEBUG"
        show_level = show_path = show_time = True
    handler = RichHandler(
        level=verbosity,
        show_time=show_time,
        show_level=show_level,
        show_path=show_path,
        markup=True,
    )
    handler.setFormatter(logging.Formatter(console_fmt))
    logging.basicConfig(level=verbosity, handlers=[handler])
    logger = logging.getLogger("steam-dumper")

    steam_dumper = SteamDumper(logger, done_event, args.debug)
    steam_dumper.run(args.refresh_list, args.fetch_missing_details)
