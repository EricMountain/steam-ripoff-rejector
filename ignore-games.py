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


def login_to_steam(driver):
    driver.get('https://store.steampowered.com/login/')

    wait = WebDriverWait(driver, 60)
    wait.until(EC.title_is("Welcome to Steam"))

    print("Logged in")


def ignore_game(driver, appid):
    game_url = f'https://store.steampowered.com/app/{appid}/'
    driver.get(game_url)
    print("Loading game page")

    # time.sleep(3)

    wait = WebDriverWait(driver, 10)
    ignoreBtn = wait.until(EC.element_to_be_clickable((By.ID, "ignoreBtn")))

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


def get_games_from_publisher(field, name):
    games = []
    path = "./data"
    for filename in next(os.walk(path), (None, None, []))[2]:
        with open(os.path.join(path, filename), 'r') as file:
            all_games = json.load(file)

        for appid, game in all_games.items():
            if name.lower() == game.get(field, '').lower():
                games.append((appid, game['name']))
                print(f"Found game: {game}")

    return games


# Initialize the browser
driver = webdriver.Chrome()

# Log in to Steam
login_to_steam(driver)

with open("games_to_ignore.yaml", "r") as f:
    games_to_ignore = yaml.safe_load(f)

    games = []
    for type in ('publisher', 'developer'):
        try:
            names = games_to_ignore[type]
        except KeyError:
            continue

        for name in names:
            print(f"Ignoring games by {type} {name}")
            g = get_games_from_publisher(type, name)
            print(g)
            print(f"Found {len(g)} games by {type} {name}")
            games.extend(g)

    for appid, name in games:
        ignore_game(driver, appid)
        print(f'Ignored {name} (appid: {appid})')

driver.quit()
