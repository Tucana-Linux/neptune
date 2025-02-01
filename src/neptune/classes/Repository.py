import os
import logging
import subprocess
import sys

import requests

from neptune import functions


class Repository:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        if not (len(self.name) >= 1 and len(self.url) >= 1) :
           logging.critical("Configuration error with repos")
           sys.exit(1)
        self.available_packages = set()
        self.versions = {}
        try:
            self.available_packages = set(open(f"{functions.cache_dir}/repos/{self.name}/available-packages", "r").read().splitlines())
            with open(f"{functions.cache_dir}/repos/{self.name}/versions", 'r') as file:
                self.versions = dict(line.strip().split(': ') for line in file if line.strip())
        except:
            logging.warning(f"{self.name} @ {self.url} has not been initalized")
           
    def check_connection(self):
       try:
          check_file = requests.head(f'{self.url}/available-packages/sha256')
          if check_file.status_code != requests.codes.ok:
             logging.warning("This does not seem to be a Tucana repo server")
             subprocess.run(f"rm -rf {functions.cache_dir}/repos/{self.name}/", shell=True)
             self.__init__(self.name, self.url)
       except requests.RequestException as e:
          logging.warning(f"Error connecting to repo {self.name}: {e}")
          subprocess.run(f"rm -rf {functions.cache_dir}/repos/{self.name}/", shell=True)
          self.__init__(self.name, self.url)
    # link_path and package are mutally exclusive
    # link path is a relative path
    def download_link(self, link_path, output_path, package=None, console_line=None):
       def make_progress_bar(progress, total, width=20):
          filled_length = int(width * progress / total)
          # i love you python string concatonation
          bar = '#' * filled_length + ' ' * (width - filled_length)
          percent = progress / total * 100
          return rf"\[{bar}] {percent:.1f}%"
       if package != None:
          link = f'{self.url}/packages/{package}.tar.xz'
          output_path = f'{functions.cache_dir}/{package}.tar.xz'
       else:
          link = f'{self.url}/{link_path}'
          
       try:
          download = requests.get(link, stream=True)
          downloaded_progress = 0

          with open(output_path, 'wb') as file:
             # performance so you don't check this on every chunk
             if console_line is not None:
                for chunk in download.iter_content(chunk_size=functions.settings.stream_chunk_size):
                   downloaded_progress += len(chunk)
                   bar = make_progress_bar(downloaded_progress, int(download.headers.get('content-length', 0)))
                   console_line.update(f"{package} Downloading {bar}")
                   file.write(chunk)
             else:
                for chunk in download.iter_content(chunk_size=functions.settings.stream_chunk_size):
                   file.write(chunk)
                #progress.update(download_task, advance=len(chunk))
       except requests.RequestException as e:
          # TODO Fix for progress bars <rahul@tucanalinux.org>
          logging.warning(f"Failed to download {link}, you have likely lost internet, error: {e}")
          subprocess.run(f"rm -f {output_path}")

    def sync(self): 
        # circular import?
        print(f"Syncing {self.name} at {self.url}")

        if not os.path.exists(path=f"{functions.cache_dir}/repos/{self.name}/"):
           logging.info(f"Creating {self.name} cache directory")
           os.makedirs(f"{functions.cache_dir}/repos/{self.name}/depend")
        logging.info(f"{self.name}: Getting Available Packages")
        self.download_link(f"available-packages/packages", f'{functions.cache_dir}/repos/{self.name}/available-packages')

        logging.info(f"{self.name}: Getting dependency files")
        self.download_link(f"depend/depends.tar.xz", f'{functions.cache_dir}/repos/{self.name}/depend/depends.tar.xz')
        os.chdir(f"{functions.cache_dir}/repos/{self.name}/depend")
        subprocess.run('tar -xf depends.tar.xz', shell=True)

        logging.info(f"{self.name}: Getting meta info")
        self.download_link(f"available-packages/sha256", f'{functions.cache_dir}/repos/{self.name}/sha256')
        self.download_link(f"available-packages/versions", f'{functions.cache_dir}/{self.name}/versions')
        # reinit
        self.__init__(self.name, self.url)

    def check_if_package_exists(self, package):
       return package in self.available_packages
        
    # Precondition, a package that exists in this repo
    def get_package_ver(self, package):
       return self.versions[package]

