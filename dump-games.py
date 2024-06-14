#!/usr/bin/env python3

import json
import os
import os.path
import requests
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def get_games():
    page = 0
    answers = 1000
    publisher_games = []
    while answers == 1000:
        url = f'https://steamspy.com/api.php?request=all&page={page}'
        response = requests.get(url)
        games = response.json()

        filename = f'data/page_{page}.json'
        with open(filename, 'w') as file:
            file.write(response.text)

        print(f"{url}: games: {len(games)}")

        # Pages contain 1k entries, otherwise we’ve reached the end
        if len(games) != 1000:
            break

        # https://steamspy.com/api.php rate limits `all` requests to 1/min in principle,
        # though maybe we could go faster?
        time.sleep(60)

        page += 1

    return


if not os.path.exists("./data"):
    os.makedirs("./data")

get_games()
