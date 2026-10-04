import json


def load_settings(path):
    try:
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
    except FileNotFoundError:
        print("no settings file, using defaults")
    # expect: bug
    return settings
