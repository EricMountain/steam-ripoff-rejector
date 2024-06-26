#!/usr/bin/env python3

import argparse
import logging
import signal
from threading import Event
import time
import yaml

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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from db import Database


class SteamIgnoreGames:
    def __init__(self, logger, done_event: Event):
        self.db = Database()
        self.logger = logger
        self.done_event = done_event

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
            TimeRemainingColumn(elapsed_when_finished=True),
        )

    # TODO: refactor this somewhere
    def ellipsise(self, name: str) -> str:
        if len(name) <= self.max_name_width:
            return name

        half = int(self.max_name_width / 2)
        remainder = self.max_name_width % 2

        left = name[: half - (1 - remainder)]
        right = name[-half:]

        return left + "…" + right

    def login_to_steam(self, driver):
        driver.get("https://store.steampowered.com/login/")

        wait = WebDriverWait(driver, 60)
        wait.until(EC.title_is("Welcome to Steam"))

        self.logger.debug("Logged in")

    def ignore_game(self, driver, appid, name):
        game_url = f"https://store.steampowered.com/app/{appid}/"
        self.logger.debug(f"Loading game page: {game_url}")
        driver.get(game_url)

        wait = WebDriverWait(driver, 10)
        ignoreBtn = wait.until(EC.element_to_be_clickable((By.ID, "ignoreBtn")))

        ignore = driver.find_element(
            By.XPATH, '//div[@id="ignoreBtn"]//span[contains(text(),"Ignore")][1]'
        )
        ignored = driver.find_element(
            By.XPATH, '//div[@id="ignoreBtn"]//span[contains(text(),"Ignored")]'
        )

        self.logger.debug(ignore, ignore.is_displayed())
        self.logger.debug(ignored, ignored.is_displayed())

        # TODO: rewrite this logic and add retries or wait until ignored is displayed iso using a sleep
        if ignored.is_displayed():
            self.logger.debug(f"{name} is already ignored, skipping")
        else:
            ignoreBtn.click()
            time.sleep(1)
            self.logger.debug(f"Ignored {name}: {ignored.is_displayed()}")
        # We want the upsert regardless
        if ignored.is_displayed():
            self.db.upsert_game_ignored(appid)

    def get_games_for_criteria(self, type, properties):
        if "kind" not in properties or "values" not in properties:
            self.logger.warning(f"No kind/values for type {type}, ignoring")
            return

        games = []
        for value in properties["values"]:
            if properties["kind"] == "list":
                games.extend(self.db.list_apps_array_filter(type, value))
            elif properties["kind"] == "value":
                games.extend(self.db.list_apps_value_filter(type, value))
            else:
                self.logger.warning(f"Unknown filter kind, ignoring: {properties}")

        return games

    def get_games_for_filters(self, filters, games, ignored_games):
        games = {}
        ignored_games = {}
        for type in filters:
            try:
                properties = filters[type]
            except KeyError:
                self.logger.warning(
                    f"Invalid configuration: no properties for type {type}, ignoring"
                )
                continue

            games_tmp = self.get_games_for_criteria(type, properties)
            if games_tmp is not None and len(games_tmp) > 0:
                self.logger.info(f"Found {len(games_tmp)} games for filter `{type}`")
                for game_tmp in games_tmp:
                    appid = game_tmp["appid"]
                    if appid not in games and not game_tmp["ignored"]:
                        games[appid] = game_tmp
                    if appid not in ignored_games and game_tmp["ignored"]:
                        ignored_games[appid] = True
        return (games, ignored_games)

    def get_games_for_queries(self, queries, games, ignored_games):
        games = {}
        ignored_games = {}
        for query in queries:
            try:
                description = query["description"]
                q = query["query"]
            except KeyError:
                self.logger.warning(
                    f"Invalid configuration: no description or query in {query}"
                )
                continue

            games_tmp = self.db.list_apps_for_query(q)
            if games_tmp is not None and len(games_tmp) > 0:
                self.logger.info(
                    f"Found {len(games_tmp)} games for query `{description}`"
                )
                for game_tmp in games_tmp:
                    appid = game_tmp["appid"]
                    if appid not in games and not game_tmp["ignored"]:
                        games[appid] = game_tmp
                    if appid not in ignored_games and game_tmp["ignored"]:
                        ignored_games[appid] = True

        return (games, ignored_games)

    def run(self, dry_run: bool):
        games = {}
        ignored_games = {}
        with open("steam-games-to-ignore.yaml", "r") as f:
            y = yaml.safe_load(f)
            map = {
                "filters": self.get_games_for_filters,
                "queries": self.get_games_for_queries,
            }
            for mode, func in map.items():
                if mode in y:
                    (games_tmp, ignored_games_tmp) = func(y[mode], games, ignored_games)
                    games |= games_tmp
                    ignored_games |= ignored_games_tmp

        ignored_total = len(ignored_games)
        self.logger.info(f"{ignored_total} unique games already ignored")

        total = len(games)
        if total == 0:
            self.logger.info("No games remaining to ignore")
            return
        self.logger.info(f"{total} unique games to ignore")

        if not dry_run:
            driver = webdriver.Chrome()
            self.login_to_steam(driver)

        with self.progress:
            task = self.progress.add_task(description="", total=total, name="")
            for appid, game in games.items():
                name = game["name"]
                self.progress.update(task, name=self.ellipsise(name))

                if not dry_run:
                    self.ignore_game(driver, appid, name)

                self.progress.update(task, advance=1)

        if not dry_run:
            driver.quit()


def handle_sigint(signum, frame):
    done_event.set()


if __name__ == "__main__":
    done_event = Event()
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(
        description="Automates ignoring Steam games according to criteria"
    )

    parser.add_argument(
        "--dry-run",
        help="Whether to actually ignore games or just list those that would be",
        type=bool,
        action=argparse.BooleanOptionalAction,
        default=True,
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
    logger = logging.getLogger("steam-ignore")

    sig = SteamIgnoreGames(logger, done_event)
    sig.run(args.dry_run)
