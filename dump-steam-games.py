#!/usr/bin/env python3

import argparse
import json
import requests
import sys
import time

from db import Database


class SteamDumper():
    def __init__(self):
        self.db = Database()

    def run(self, refresh_list: bool, fetch_missing_details: bool):
        if refresh_list:
            self.refresh_list()

        if fetch_missing_details:
            self.fetch_missing_details()

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
        # 1" is too short, but 2" works fine
        sleep_time = 1.1
        penalty = 0.1
        grace = 0.01
        rate_limit_upper_bound_sleep_time = 0

        appids = self.db.list_apps_missing_details()
        app_count = self.db.get_app_count()
        missing_count = len(appids)
        missing_pct = missing_count * 100 / app_count
        print(f"Total missing {missing_count}, {missing_pct:.2f}%")
        fetched = 0
        for appid_row in appids:
            appid = appid_row['appid']
            name = appid_row['name']
            print(f"Fetching details for {name} / {appid}")
            url = f"https://store.steampowered.com/api/appdetails?appids={
                appid}"
            retry = True
            while retry:
                retry = False
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Unexpected server response code {
                          response.status_code}: {response.headers}")
                    if response.status_code == 429:
                        # Rate limited
                        rate_limit_upper_bound_sleep_time = sleep_time
                        sleep_time += penalty
                        print(f"Rate limit penalty applied. Sleep time: {
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
                if fetched % 100 == 0:
                    sleep_time_tmp = sleep_time - grace
                    if sleep_time_tmp > rate_limit_upper_bound_sleep_time:
                        sleep_time = sleep_time_tmp

                    missing_tmp = missing_count - fetched
                    missing_tmp_pct = missing_tmp * 100 / app_count
                    print(f'Total missing {missing_tmp} / {
                          missing_tmp_pct:.2f}%. Sleep time: {sleep_time}')

                time.sleep(sleep_time)


if __name__ == '__main__':
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

    args = parser.parse_args()
    print(f"{args}")

    steam_dumper = SteamDumper()
    steam_dumper.run(args.refresh_list, args.fetch_missing_details)
