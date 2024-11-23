from pathlib import Path
import subprocess
import sys
import os
import requests
from neptune import functions
from neptune import sync


arguments = list(sys.argv)
arguments.pop(0)
path = ""
cache_dir = ""

yes_mode = False
def parse_arguments():
  valid_cli_arguments = ["--y"]
  cooresponding = [yes_mode]

  if len(arguments) == 0:
     usage="""Usage: neptune-bootstrap [path] [flags]
   Flags:
       --y: Temporarily disables confirmation with all operations that require one
           """
     print(usage)
     sys.exit(0)
  global path
  path = arguments[0]
  arguments.pop(0)
  for arg in range(len(valid_cli_arguments)):
    if valid_cli_arguments[arg] in arguments:
      cooresponding[arg] = True
      # How many packages could you possibly pass? probably fine to use remove
      arguments.remove(cooresponding[arg])

def generate_file_list(package):
    os.chdir(f'{cache_dir}/{package}')
    # This is a bash oneliner, I know it isn't ideal but it's easier to read than the python alternative
    subprocess.run(f'find * -type f | sed \'s|^|/|g\' > {cache_dir}/file-lists/{package}.list', shell=True)
    os.chdir(cache_dir)
def check_for_and_delete(path_to_delete):
   if os.path.exists(path_to_delete):
      subprocess.run(f'rm -f {path_to_delete}/', shell=True)
def copy_files(package):
   subprocess.run(f'cp -rp {package}/* {path}', shell=True)
   for i in ['depends', 'depend', 'make-depend', 'make-depends', 'postinst', 'preinst', 'prerm', 'preupdate']:
      check_for_and_delete(f'{path}/{i}')

def download_link(link, output_path):
   try:
      download = requests.get(link, stream=True)
      with open(output_path, 'wb') as file:
         # use streams as these can get big
         for chunk in download.iter_content(chunk_size=8192):
            file.write(chunk)
   except requests.RequestException as e:
      print(f"Failed to download {link}, you have likely lost internet, error: {e}")
      subprocess.run(f"rm -f {output_path}")
      sys.exit(1)

def download_package(package):
   print(f"Downloading {package}")
   download_link(f'{functions.repo}/packages/{package}.tar.xz', f'{cache_dir}/{package}.tar.xz')

def install_package(package):
   if not os.path.exists(cache_dir):
      os.makedirs(cache_dir)
   os.chdir(cache_dir)

   download_package(package)
   
   print(f"Extracting {package}")
   subprocess.run(f'tar -xpf {package}.tar.xz', shell=True)

   print(f"Generating File List for {package}")
   generate_file_list(package)

   print("Installing files")
   copy_files(package)
   
   if package != "base":
      open(f'{path}/etc/installed_package', 'a').write(package + "\n")
   else:
      open(f'{path}/etc/installed_package', 'a').write("base-update\n")
   print("Removing Cache")
   subprocess.run(f'rm -rf {package}', shell=True)
   subprocess.run(f'rm -f {package}.tar.xz', shell=True)

def install_packages(packages):
   for package in packages:
      install_package(package)

def create_inital_files():
   os.makedirs(cache_dir)
   os.makedirs(f'{cache_dir}/file-lists')
   os.makedirs(f'{cache_dir}/depend')
   try: 
      sha256 = requests.get(f'{functions.repo}/available-packages/sha256', allow_redirects=True)
      open(f'{cache_dir}/current', 'wb').write(sha256.content)
   except:
      print("Error retreiving files from the repository is it online?")
      sys.exit(1)
   subprocess.run(f'cp {cache_dir}/current {cache_dir}/sha256', shell=True)


def bootstrap():
   # This is a complete reimplmentation, neptune main never gets called here.
   functions.check_online()
   parse_arguments()
   if not os.listdir(path) == []:
      print("This directory is not empty!")
      sys.exit(1)
   global cache_dir
   cache_dir = f'{path}/var/cache/mercury'
   print("Syncing")
   sync()
   create_inital_files()

   print("Getting dependencies")
   packages=functions.get_depends(["base"], check_installed=False)
   if not functions.yes_mode:
      print(f"Packages to install: {" ".join(packages)}") 
      confirmation=input(f"You are about to bootstrap {path}, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   install_packages(packages)
   open(f'{path}/etc/wanted_package', 'a').write("base-update\n")

