#!/usr/bin/env bash

python3 -m venv auto-process
source auto-process/bin/activate
pip install --upgrade pip wheel
pip install --upgrade mx-autoprocess
