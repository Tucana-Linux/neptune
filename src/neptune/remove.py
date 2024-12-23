import subprocess
import sys
import os

from neptune import functions

def calculate_removed_dependencies(packages_to_remove):
   future_wanted_packages = set(open(f"{functions.settings.install_path}/etc/wanted_packages", "r").read().splitlines())
   for package in packages_to_remove:
      future_wanted_packages.remove(package)
   depends_of_wanted_packages = functions.get_depends(future_wanted_packages, False)
   remove = [pkg for pkg in functions.installed_packages if pkg not in depends_of_wanted_packages]
   return remove
    
def remove():
   if not len(functions.arguments) > 0:
      print("Usage: neptune-remove {{PACKAGES}}") 
      sys.exit(1)
   # Only remove wanted packages
   wanted_packages = set(open(f"{functions.settings.install_path}/etc/wanted_packages", "r").read().splitlines())
   for package in functions.arguments:
      if not (package in functions.installed_packages):
         print(f"{package} is not installed")
         sys.exit(0)
      if not (package in wanted_packages):
         print(f"{package} was installed as a dependency of another package, it can not be removed sanely")
         sys.exit(1)
   to_remove = calculate_removed_dependencies(functions.arguments)
   if not functions.settings.yes_mode:
      print(f"Packages to be removed: {" ".join(to_remove)}")
      confirmation=input(f"{len(to_remove)} packages are queued to remove, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.remove_packages(to_remove, "other")
   subprocess.run(f"sed -i '/{package}/d' {functions.settings.install_path}/etc/wanted_packages")
