# Ignore publishers and developers you don’t like on Steam

## Use

* Install required modules, e.g. `pip3 install -r requirements.txt`.
* Run `./dump-games.py`. This will take a while as we respect SteamSpy’s 1/min [ratelimit](https://steamspy.com/api.php) on `all` requests.
    * This only needs to be run the first time and any time you need to update the locally cached list of games.
* List the publishers and developers you want to ignore in `games_to_ignore.yaml`.
* Run `./ignore-games.py`.
* Login to Steam on the browser window that opens under Selenium’s control.
* Enjoy the automation.

## Thanks

Thanks to [SteamSpy](https://steamspy.com) for making the list of games on Steam available.



select appid, json_extract(details, '$.data.name') from steam_app_details, json_each(details, '$.data.publishers') where json_each.value = 'Valve';
select appid, json_extract(details, '$.data.name') from steam_app_details where details -> '$.data.support_info.url' like '%http://steamcommunity.com/app/%';
