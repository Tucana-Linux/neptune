import sys
from neptune import functions

def install():
   if not len(functions.arguments) > 0:
      print("Usage: neptune-install {{PACKAGES}}") 
      sys.exit(1)
   functions.check_if_packages_exist(functions.arguments)
   print("Getting dependencies")
   packages_to_install=functions.get_depends(functions.arguments, check_installed=True)
   if len(packages_to_install) == 0:
      print("Nothing to do all packages are installed")
      sys.exit()
   if not functions.settings.yes_mode:
      print(f"Packages to install: {" ".join(packages_to_install)}")
      confirmation=input(f"{len(packages_to_install)} packages are queued to install, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.install_packages(packages_to_install, "install")
   for package in functions.arguments:
      with open(f'{functions.settings.lib_dir}/wanted_packages', 'a') as wanted_packages:
         wanted_packages.write(package + "\n")
