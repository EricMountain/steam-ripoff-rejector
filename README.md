# Ignore publishers and developers you don’t like on Steam

## Use

* List the publishers and developers you want to ignore in `games_to_ignore.yaml`.
* Run `./dump-games.py`. This will take a while as we respect SteamSpy’s 1/min [ratelimit](https://steamspy.com/api.php) on `all` requests.
* Run `./ignore-games.py`.
* Login to Steam on the browser window that opens under Selenium’s control.
* Enjoy the automation.

## Thanks

Thanks to [SteamSpy](https://steamspy.com) for making the list of games on Steam available.
