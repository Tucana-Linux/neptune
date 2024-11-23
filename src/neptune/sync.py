import subprocess
import os
import requests
from neptune import functions
# initally refactored from mercury-sync
def sync():
    os.chdir(f'{functions.cache_dir}/depend')
    print("Getting Available Packages")
    available_packages=requests.get(f"{functions.repo}/available-packages/packages")
    open(f'{functions.cache_dir}/available-packages', 'wb').write(available_packages.content)

    print("Getting dependency files")
    depends=requests.get(f"{functions.repo}/available-packages/packages")
    open(f'{functions.cache_dir}/depend/depends.tar.xz', 'wb').write(depends.content)
    subprocess.run('tar -xpf depends.tar.xz', shell=True)

    print("Getting meta info")
    sha256=requests.get(f"{functions.repo}/available-packages/packages")
    open(f'{functions.cache_dir}/sha256', 'wb').write(sha256.content)


