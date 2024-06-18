# Ignore publishers and developers you don’t like on Steam

## Use

* Install required modules, e.g. `pip3 install -r requirements.txt`.
* Run `./dump-steam-games.py --refresh-list --fetch-missing-details `.
    * This will take a few days to achieve a complete run due to rate-limiting on the API to fetch game details and cache them in SQLite.
    * This only needs to be run the first time and any time you need to update the locally cached list of games.
* List the publishers and developers you want to ignore in `steam-games-to-ignore.yaml`.
* Run `./ignore-steam-games.py`.
* Login to Steam on the browser window that opens under Selenium’s control.
* Enjoy the automation.
