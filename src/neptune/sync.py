import subprocess
import os
import requests
from neptune import functions
# initally refactored from mercury-sync
def sync():
    os.chdir(f'{functions.cache_dir}/depend')
    print("Getting Available Packages")
    functions.download_link(f"{functions.settings.repo}/available-packages/packages", f'{functions.cache_dir}/available-packages')

    print("Getting dependency files")
    functions.download_link(f"{functions.settings.repo}/depend/depends.tar.xz", f'{functions.cache_dir}/depend/depends.tar.xz')
    subprocess.run('tar -xf depends.tar.xz', shell=True)

    print("Getting meta info")
    functions.download_link(f"{functions.settings.repo}/available-packages/sha256", f'{functions.cache_dir}/sha256')


