import subprocess
import os
import requests
from neptune import functions
# initally refactored from mercury-sync
def sync():
    for repo in functions.settings.repositories:
        repo.sync()


