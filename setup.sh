#!/bin/bash
sudo apt update
sudo apt install -y python3
sudo apt install -y python3-pip
sudo apt install -y python-is-python3
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt