import sqlite3

from dataclasses import dataclass

import db.schema_upgrades


@dataclass()
class MaintainSchema:
    connection: sqlite3.Connection
    target_schema_version: int = 0

    def __post_init__(self):
        self.get_schema_version()
        self.upgrade_schema()

    def upgrade_schema(self):
        assert self.schema_version <= self.target_schema_version
        if self.schema_version == self.target_schema_version:
            return

        print(
            f"Processing schema upgrades from v{self.schema_version} to v{self.target_schema_version}"
        )
        for v in range(self.schema_version + 1, self.target_schema_version + 1):
            print(f"Upgrading schema to v{v}")
            class_ = getattr(db.schema_upgrades, f"SchemaUpgradeV{v}")
            class_(self.connection)
        self.get_schema_version()
        assert self.schema_version == self.target_schema_version

    def get_schema_version(self) -> int:
        self.ddl_create_table_steam_metadata()

        schema_version_str = ""
        with self.connection:
            cursor = self.connection.cursor()
            query = """
                  select value
                  from steam_metadata
                  where key = 'schema_version'
                  """
            cursor.execute(query)

            for row in cursor:
                schema_version_str = row["value"]

            if schema_version_str == "":
                schema_version_str = "-1"
                self.connection.execute("""insert into steam_metadata(key, value)
                                        values('schema_version', '-1')
                                    """)

        self.schema_version = int(schema_version_str)

    def ddl_create_table_steam_metadata(self):
        self.connection.execute("""create table if not exists steam_metadata (
                                 key text not null primary key,
                                 value text not null
                                 )
                              """)
