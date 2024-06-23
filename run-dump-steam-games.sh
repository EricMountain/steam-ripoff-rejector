#!/usr/bin/env bash

set -euo pipefail

pipenv --venv || pipenv install

pipenv run ./dump-steam-games.py --refresh-list --fetch-missing-details
