#!/bin/python3
import subprocess
import sys
import os
import requests
import yaml

if os.geteuid() != 0:
   print("This package manager must be run as root")
   sys.exit()

# Should be moved to the config file
with open('/etc/neptune/config.yaml', 'r') as config_file:
   config= yaml.safe_load(config_file)
repo = config['repositories'][0]
install_path = config['system-settings']['install_path']
yes_mode = config['system-settings']['yes_mode_by_default']
stream_chunk_size = config['system-settings']['stream_chunk_size']



# Global vars
cache_dir = f'{install_path}/var/cache/mercury'
postinstalls = []
packages=[]
packages_set = set()
operation = ""


try:
   available_packages = set(open(f"{cache_dir}/available-packages", "r").read().splitlines())
   installed_packages = set(open(f"{install_path}/etc/installed_package", "r").read().splitlines())
except FileNotFoundError:
   print("Unless you are installing Tucana by-hand (in which case run sync), you have a serious problem")
   print("Either the installed_packages file or the available_packages file is missing, one is much worse than the other")
   sys.exit(1)


# Argument stuff
no_depend_mode = False
arguments = list(sys.argv)
arguments.pop(0)

'''
Universal Functions
'''

def check_online():
   try:
      check_file = requests.head(f'{repo}/available-packages/sha256')
      if check_file.status_code != requests.codes.ok:
         print("This does not seem to be a Tucana repo server")
         sys.exit(1)
   except requests.RequestException as e:
      print(f"Error connecting to repo server: {e}")
      sys.exit(1)

def generate_file_list(package):
    os.chdir(f'{cache_dir}/{package}')
    # This is a bash oneliner, I know it isn't ideal but it's easier to read than the python alternative
    subprocess.run(f'find * -type f | sed \'s|^|/|g\' > {cache_dir}/file-lists/{package}.list', shell=True)
    os.chdir(cache_dir)

def postinst():
   for package in postinstalls:
      print(f"Running {package} post-install")
      subprocess.run(f"bash /tmp/{package}-postinst", shell=True)
      subprocess.run(f'rm -f /tmp/{package}-postinst', shell=True)
def download_link(link, output_path):
   try:
      download = requests.get(link, stream=True)
      with open(output_path, 'wb') as file:
         # use streams as these can get big
         for chunk in download.iter_content(chunk_size=stream_chunk_size):
            file.write(chunk)
   except requests.RequestException as e:
      print(f"Failed to download {link}, you have likely lost internet, error: {e}")
      subprocess.run(f"rm -f {output_path}")
      sys.exit(1)

def download_package(package):
   print(f"Downloading {package}")
   download_link(f'{repo}/packages/{package}.tar.xz', f'{cache_dir}/{package}.tar.xz')
   

def check_for_and_delete(path_to_delete):
   if os.path.exists(path_to_delete):
      subprocess.run(f'rm -f {path_to_delete}/', shell=True)

def copy_files(package):
   subprocess.run(f'cp -rp {package}/* {install_path}', shell=True)
   for i in ['depends', 'depend', 'make-depend', 'make-depends', 'postinst', 'preinst', 'prerm', 'preupdate']:
      check_for_and_delete(f'{install_path}/{i}')

def update_files(package):
   # needed for updates & reinstalls
   os.chdir(f'{cache_dir}/{package}')
      # Find all the directories and create them if they don't exist
   for root, dirs, files in os.walk(f'.'):
      for dir_name in dirs:
         folder_path = os.path.join(install_path, os.path.join(root, dir_name).lstrip('.'))
         os.makedirs(folder_path, exist_ok=True)
      for file in files:
         if file in ('postinst', 'depends'):
            continue
         file_path = os.path.join(install_path, os.path.join(root, file).lstrip('.'))
         subprocess.run(f'mv {os.path.join(root, file)} {file_path}', shell=True)
   os.chdir(cache_dir)

def install_package(package, operation):
   if not os.path.exists(cache_dir):
      os.makedirs(cache_dir)
   os.chdir(cache_dir)
   
   download_package(package)

   print(f"Extracting {package}")
   subprocess.run(f'tar -xpf {package}.tar.xz', shell=True)

   print(f"Generating File List for {package}")
   generate_file_list(package)

   print("Installing files")
   match operation:
      case "install":
         copy_files(package)
      case "other":
         update_files(package)
   
   if os.path.exists(f'{package}/postinst'):
      postinstalls.append(package)
      subprocess.run(f'cp {package}/postinst /tmp/{package}-postinst', shell=True)
   if package != "base":
      open(f'{install_path}/etc/installed_package', 'a').write(package + "\n")
   else:
      open(f'{install_path}/etc/installed_package', 'a').write("base-update\n")
   print("Removing Cache")
   subprocess.run(f'rm -rf {package}', shell=True)
   subprocess.run(f'rm -f {package}.tar.xz', shell=True)

def install_packages(packages, operation):
   for package in packages:
      install_package(package, operation)
   postinst()

def check_if_packages_exist(packages):
   # This is easier as a shell command
   for package in packages:
      if not package in available_packages:
         print(f'{package} was not found, exiting')
         sys.exit(1)

def check_if_package_installed(package, check):
   if not check:
      return False
   return package in installed_packages

def get_depends(temp_packages, check_installed):
   if len(temp_packages) == 0:
      return packages
   for package in temp_packages:
      # the check_installed is to avoid mutliple functions or ifs, it just makes check_if_package_installed return false if it is false.
      if not (package in packages_set or check_if_package_installed(package, check_installed)):
         packages.append(package)
         packages_set.add(package)
         try:
            depends=[]
            with open(f'{cache_dir}/depend/depend-{package}', 'r') as depend_file:
               depends = depend_file.read().split()
         except FileNotFoundError:
            print(f"{package} depends file NOT found, something is SERIOUSLY WRONG")
            continue
         # Validate then recurse
         check_if_packages_exist(depends)
         get_depends(depends, check_installed)
   return packages


def recalculate_system_depends():
   remove = []
   # check to see if anything currently installed is no longer avaliable
   for package in installed_packages:
      if not (package in available_packages):
         print(f"{package} no longer exists")
         remove.append(package)
         subprocess.run(f'sed -i \'/{package}/d\' {install_path}/etc/wanted_packages', shell=True)
   # this isn't global because sync doesn't create this file
   wanted_packages = set(open(f"{install_path}/etc/wanted_packages", "r").read().splitlines())
   depends_of_wanted_packages = get_depends(wanted_packages, check_installed=False)

   install = [pkg for pkg in depends_of_wanted_packages if pkg not in installed_packages]
   remove += [pkg for pkg in installed_packages if pkg not in depends_of_wanted_packages]
   return [install, remove]

def remove_package(package):
   # Depend checking is handled in the remove.py file, this is actually removing the program
   # therefore use this function with caution
   try:
      files = set(open(f"{cache_dir}/file-lists/{package}.list", "r").read().splitlines())
   except FileNotFoundError:
      print(f"File list for {package} not found, skipping removal")
      return
   print(f"Removing {package}")
   for file in files:
      # os/subprocesses remove function will crash the system if it's removing something that is currently in use
      check_for_and_delete(f'{install_path}/{file}', shell=True)
   # Sed's are easier to understand
   # it's removed from wanted in remove.py
   subprocess.run(f"sed -i '/{package}/d' {install_path}/etc/installed_package" , shell=True)

def remove_packages(packages):
   for package in packages:
      remove_package(package)




