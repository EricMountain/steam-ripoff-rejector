#!/usr/bin/env python3

import json
import os
import os.path
import requests
import time
import yaml

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from db import Database


class SteamIgnoreGames():
    def __init__(self):
        self.db = Database()

    def login_to_steam(self, driver):
        driver.get('https://store.steampowered.com/login/')

        wait = WebDriverWait(driver, 60)
        wait.until(EC.title_is("Welcome to Steam"))

        print("Logged in")

    def ignore_game(self, driver, appid):
        game_url = f'https://store.steampowered.com/app/{appid}/'
        driver.get(game_url)
        print("Loading game page")

        wait = WebDriverWait(driver, 10)
        ignoreBtn = wait.until(
            EC.element_to_be_clickable((By.ID, "ignoreBtn")))

        ignore = driver.find_element(
            By.XPATH, '//div[@id="ignoreBtn"]//span[contains(text(),"Ignore")][1]')
        ignored = driver.find_element(
            By.XPATH, '//div[@id="ignoreBtn"]//span[contains(text(),"Ignored")]')

        print(ignore, ignore.is_displayed())
        print(ignored, ignored.is_displayed())

        if ignored.is_displayed():
            print("Game is already ignored, skipping")
        else:
            ignoreBtn.click()
            time.sleep(1)
            print("Ignoring game", ignored.is_displayed())

    def get_games_from_publisher(self, type, properties):
        games = []
        for value in properties['values']:
            if properties['kind'] == 'list':
                games.extend(self.db.list_apps_array_filter(type, value))
            elif properties['kind'] == 'value':
                games.extend(self.db.list_apps_value_filter(type, value))
            else:
                print(f"Unknown filter kind: {properties}")

        return games

    def run(self):
        # Initialize the browser
        # driver = webdriver.Chrome()

        # Log in to Steam
        # self.login_to_steam(driver)

        with open("steam-games-to-ignore.yaml", "r") as f:
            games_to_ignore = yaml.safe_load(f)

            games = []
            for type in games_to_ignore:
                print(type, games_to_ignore[type])
                try:
                    properties = games_to_ignore[type]
                except KeyError:
                    continue

                g = self.get_games_from_publisher(type, properties)
                print(g)
                print(f"Found {len(g)} games by {type} {properties}")
                games.extend(g)

            # for appid, name in games:
            #     self.ignore_game(driver, appid)
            #     print(f'Ignored {name} (appid: {appid})')

        # driver.quit()


if __name__ == '__main__':
    sig = SteamIgnoreGames()
    sig.run()
