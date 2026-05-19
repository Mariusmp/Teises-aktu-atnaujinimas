#!/bin/bash
export SPREADSHEET_ID="test_sheet_id"
export DRIVE_FOLDER_ID="test_folder_id"
export RANGE_NAME="Sheet1!A:B"
python3 -m unittest test_TA_update.py
python3 -m unittest test_ta_update.py
