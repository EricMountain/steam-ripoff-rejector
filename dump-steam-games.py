#!/usr/bin/env python3

import argparse
import json
import requests
import signal
import sys
from threading import Event
import time

import rich
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)

from db import Database


class SteamDumper():
    def __init__(self, debug, done_event):
        self.db = Database()
        self.debug = debug
        self.done_event = done_event

        width = rich.console.Console().width
        self.max_name_width = int(width / 4)

        self.progress = Progress(
            SpinnerColumn(spinner_name='moon'),
            TextColumn(
                "[bold blue]{task.fields[name]:" + str(self.max_name_width) + "}", justify="right"),
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

    def debug_print(self, *args, **kwargs):
        if self.debug:
            print(*args, **kwargs)

    def ellipsise(self, name: str) -> str:
        if len(name) <= self.max_name_width:
            return name

        half = int(self.max_name_width / 2)
        remainder = self.max_name_width % 2

        left = name[:half-(1-remainder)]
        right = name[-half:]

        return left + "…" + right

    def refresh_list(self):
        url = 'http://api.steampowered.com/ISteamApps/GetAppList/v0002/?format=json'
        response = requests.get(url)
        applist = response.json()

        self.db.connection.execute("BEGIN")
        for app in applist['applist']['apps']:
            appid = app['appid']
            name = app['name']
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
        self.debug_print(f"Total missing {missing_count}, {missing_pct:.2f}%")
        fetched = 0

        with self.progress:
            task = self.progress.add_task(
                description="", total=app_count, completed=app_count-missing_count, name="Fetch missing details", sleep=sleep_time)
            for appid_row in appids:
                if self.done_event.is_set():
                    return

                appid = appid_row['appid']
                name = appid_row['name']
                self.progress.update(
                    task, completed=app_count-missing_count+fetched, name=self.ellipsise(name), sleep=sleep_time)
                self.debug_print(f"Fetching details for {name} / {appid}")
                url = f"https://store.steampowered.com/api/appdetails?appids={
                    appid}"
                retry = True
                while retry:
                    retry = False
                    response = requests.get(url)
                    if response.status_code != 200:
                        self.debug_print(f"Unexpected server response code {
                            response.status_code}: {response.headers}")
                        if response.status_code == 429:
                            # Rate limited
                            rate_limit_upper_bound_sleep_time = sleep_time
                            sleep_time += penalty
                            self.debug_print(f"Rate limit penalty applied. Sleep time: {
                                sleep_time}")
                            time.sleep(120)
                            retry = True
                        else:
                            # Pause and skip, we’ll retry next run anyway
                            time.sleep(30)
                            break
                else:
                    appdetails = response.json()
                    for appid in appdetails:
                        self.db.upsert_app_details(
                            appid, json.dumps(appdetails[appid]))

                    fetched += 1
                    self.progress.update(
                        task, completed=app_count-missing_count+fetched, name=self.ellipsise(name), sleep=sleep_time)
                    if fetched % 100 == 0:
                        sleep_time_tmp = sleep_time - grace
                        if sleep_time_tmp > rate_limit_upper_bound_sleep_time:
                            sleep_time = sleep_time_tmp

                        missing_tmp = missing_count - fetched
                        missing_tmp_pct = missing_tmp * 100 / app_count
                        self.debug_print(f'Total missing {missing_tmp} / {
                            missing_tmp_pct:.2f}%. Sleep time: {sleep_time}')

                    time.sleep(sleep_time)


def handle_sigint(signum, frame):
    done_event.set()


if __name__ == '__main__':
    done_event = Event()
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(
        description='Dumps Steam games to a local database')

    parser.add_argument("--refresh-list",
                        help="Whether to fetch the full list of games from Steam",
                        type=bool,
                        action=argparse.BooleanOptionalAction,
                        default=False)

    parser.add_argument("--fetch-missing-details",
                        help="Whether to fetch details for apps that are missing them",
                        type=bool,
                        action=argparse.BooleanOptionalAction,
                        default=False)
    parser.add_argument("--debug",
                        help="Verbose/debug mode",
                        type=bool,
                        action=argparse.BooleanOptionalAction,
                        default=False)

    args = parser.parse_args()

    steam_dumper = SteamDumper(args.debug, done_event)
    steam_dumper.run(args.refresh_list, args.fetch_missing_details)
