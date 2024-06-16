import sqlite3
import os
import time
from datetime import datetime, timezone

from dataclasses import dataclass

from .ddl import MaintainSchema


@dataclass
class Database():

    def __post_init__(self):
        self.db_path = "data/steam.db"

        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

        MaintainSchema(self.connection)

    def add_app(self, appid: int, name: str):
        # Used inside a transaction, so no `with`
        cursor = self.connection.cursor()
        query = '''
                insert or ignore into steam_apps(appid, name)
                values(?,?)
                '''
        cursor.execute(query, (appid, name))

    def get_app_count(self) -> int:
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select count(*) count
                  from steam_apps
                  '''
            cursor.execute(query)

            return next(cursor)["count"]

    def list_apps_missing_details(self):
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select sa.appid appid, sa.name name
                  from steam_apps sa left join steam_app_details sad on (sa.appid = sad.appid)
                  where sad.appid is null
                  '''
            cursor.execute(query)

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        return entries

    def upsert_app_details(self, appid: int, details: any):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into steam_app_details(appid, details)
                  values(?,jsonb(?))
                  on conflict(appid) do
                  update set
                    details = jsonb(?)
                  '''
            cursor.execute(query, (appid, details, details))

    def list_apps_array_filter(self, key: str, value: str):
        entries = []
        key_param = f"$.data.{key}"
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select appid, json_extract(details, '$.data.name') name
                  from steam_app_details, json_each(details, ?)
                  where json_each.value = ?
                  '''
            cursor.execute(query, (key_param, value))

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        return entries

    def list_apps_value_filter(self, key: str, value: str):
        entries = []
        key_param = f"$.data.{key}"
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select appid, json_extract(details, '$.data.name') name
                  from steam_app_details
                  where json_extract(details, ?) = ?
                  '''
            cursor.execute(query, (key_param, value))

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        return entries

    def upsert_game_ignored(self, appid: int):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into steam_apps_ignored(appid, ignored)
                  values(?, 'Y')
                  on conflict(appid) do
                  update set
                    ignored = 'Y'
                  '''
            cursor.execute(query, (appid,))
