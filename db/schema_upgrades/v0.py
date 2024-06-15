import sqlite3

from dataclasses import dataclass

from .schema_upgrade import SchemaUpgrade


@dataclass()
class SchemaUpgradeV0(SchemaUpgrade):
    connection: sqlite3.Connection
    schema_version: int = 0

    def __post_init__(self):
        self.upgrade()
        self.set_version()

    def upgrade(self):
        self.ddl_create_table_steam_apps()
        self.ddl_create_table_steam_app_details()

    def ddl_create_table_steam_apps(self):
        self.connection.execute('''create table if not exists steam_apps (
                                 appid integer primary key,
                                 name text not null
                                 )
                              ''')
        self.connection.execute('''create index if not exists steam_apps_1 on steam_apps (
                                 name,
                                 appid
                                 )
                              ''')

    def ddl_create_table_steam_app_details(self):
        self.connection.execute('''create table if not exists steam_app_details (
                                 appid integer primary key,
                                 details blob not null
                                 )
                              ''')