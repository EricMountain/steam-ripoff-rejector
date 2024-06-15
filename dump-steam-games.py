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
        appids = self.db.list_apps_missing_details()
        print(f"total missing {len(appids)}")
        for appid_row in appids:
            appid = appid_row['appid']
            print(f"missing {appid}")
            url = f"https://store.steampowered.com/api/appdetails?appids={
                appid}"
            retry = True
            while retry:
                retry = False
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"{response.status_code}: {response.headers}")
                    if response.status_code == 429:
                        time.sleep(300)
                        retry = True
                    else:
                        sys.exit(1)
            appdetails = response.json()
            for appid in appdetails:
                self.db.upsert_app_details(
                    appid, json.dumps(appdetails[appid]))
            time.sleep(2)


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
