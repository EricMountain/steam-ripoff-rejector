#!/usr/bin/env bash

set -euo pipefail

pipenv --venv || pipenv install

pipenv run ./ignore-steam-games.py "$@"
