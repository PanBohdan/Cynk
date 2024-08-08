from secret_files import *
import os
from db import items
if __name__ == '__main__':
    # if pistols or smgs
    items.update_many(
        {"stat": {"$in": ["grenade_launchers", "manpads", "atgms"]}, "type": "weapon"},
        {'$set': {'stat': "grenade_launchers_and_manpads_and_atgms"}},
    )