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

def copy_files(package):
   subprocess.run(f'cp -rp {package}/* {path}', shell=True)
   subprocess.run(f'rm -f {path}/depends')
   subprocess.run(f'rm -f {path}/depend')
   subprocess.run(f'rm -f {path}/make-depend')
   subprocess.run(f'rm -f {path}/make-depends')
   subprocess.run(f'rm -f {path}/postinst')
   subprocess.run(f'rm -f {path}/preinst')
   subprocess.run(f'rm -f {path}/prerm')
   subprocess.run(f'rm -f {path}/preupdate')

def install_package(package):
   if not os.path.exists(cache_dir):
      os.makedirs(cache_dir)
   os.chdir(cache_dir)
   
   functions.download_package(package)

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

def install_packages(packages, operation):
   for package in packages:
      install_package(package, operation)



def bootstrap():
   parse_arguments()
   global cache_dir
   cache_dir = f'{path}/var/cache/mercury'

   print("Syncing")
   sync()

   print("Getting dependencies")
   packages=functions.get_depends("base", check_installed=True)
   if not functions.yes_mode:
      print(f"Packages to install: {" ".join(packages)}") 
      confirmation=input(f"{len(packages)} ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   install_packages(packages, "install")


