import os
import sys
from neptune.classes.System import System


class Frontend:

    '''
    The direct programs run by users
    '''

    def __init__(self, system: System):
        self.system : System = system

    def install(self):
       arguments = self.system.settings.arguments
       if not len(arguments) > 0:
          print("Usage: neptune-install {{PACKAGES}}") 
          sys.exit(1)
       if not self.system.utils.check_if_packages_exist(arguments):
          print("Packages not found")
          sys.exit(1)
       print("Getting dependencies")
       packages_to_install=self.system.utils.get_depends(arguments, check_installed=True, installed_packages=self.system.installed_packages)
       if len(packages_to_install) == 0:
          print("Nothing to do all packages are installed")
          sys.exit()
       if not self.system.settings.yes_mode:
          print(f"Packages to install: {" ".join(packages_to_install)}")
          confirmation=input(f"{len(packages_to_install)} packages are queued to install, would you like to continue? [Y/n] ")
          if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
             print("Aborting")
             sys.exit(0)
       self.system.install_packages(packages_to_install)
       for package in arguments:
          with open(f'{self.system.settings.lib_dir}/wanted_packages', 'a') as wanted_packages:
             wanted_packages.write(package + "\n")

    def reinstall(self):
       arguments = self.system.settings.arguments
       if not len(arguments) > 0:
          print("Usage: neptune-reinstall {{PACKAGES}}") 
          sys.exit(1)
       for package in arguments:
          if package not in self.system.installed_packages:
             print(f'{package} is not installed!')
             sys.exit(1)
       if not self.system.settings.yes_mode:
          print(f"Packages to be reinstall: {" ".join(arguments)}")
          confirmation=input(f"{len(arguments)} packages are queued to install, would you like to continue? [Y/n] ")
          if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
             print("Aborting")
             sys.exit(0)
       self.system.install_packages(arguments, reinstalling=True)

    def update(self):
       updates = self.system.utils.check_for_updates(installed_packages=self.system.installed_packages, versions=self.system.versions)
       recalculated_depends = self.system.recalculate_system_depends()
       install = recalculated_depends[0]
       remove = recalculated_depends[1]
   
       if len(updates) == 0:
          print("No updates found, try to sync")
          sys.exit(0)
       if not self.system.settings.yes_mode:
          print(f"Packages to be updated: {" ".join(updates)}")
          if len(install) > 0:
             print(f'Packages to be installed: {" ".join(install)}')
          if len(remove) > 0:
             print(f'Packages to be REMOVED: {" ".join(remove)}')
          confirmation=input(f"Would you like to continue? [Y/n] ")
          if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
             print("Aborting")
             sys.exit(0)
       if len(install) > 0:
          self.system.install_packages(install, "install")
       self.system.install_packages(updates, "other")
       if len(remove) > 0:
          self.system.remove_packages(remove)

    def remove(self):
       if not len(self.system.settings.arguments) > 0:
          print("Usage: neptune-remove {{PACKAGES}}") 
          sys.exit(1)
       # Only remove wanted packages
       wanted_packages = set(open(f"{self.system.settings.lib_dir}/wanted_packages", "r").read().splitlines())
       for package in self.system.settings.arguments:
          if not (package in self.system.installed_packages):
             print(f"{package} is not installed")
             sys.exit(0)
          if not (package in wanted_packages):
             print(f"{package} was installed as a dependency of another package, it can not be removed sanely")
             sys.exit(1)
       to_remove = self.system.utils.calculate_removed_dependencies(self.system.settings.arguments, self.system.wanted_packages, self.system.installed_packages)
       if not self.system.settings.yes_mode:
          print(f"Packages to be removed: {" ".join(to_remove)}")
          confirmation=input(f"{len(to_remove)} packages are queued to remove, would you like to continue? [Y/n] ")
          if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
             print("Aborting")
             sys.exit(0)
       self.system.remove_packages(to_remove)
       file_path = os.path.join(self.system.settings.lib_dir, "wanted_packages")
       with open(file_path, "r") as f:
           lines = f.readlines()

       with open(file_path, "w") as f:
           for line in lines:
               if package not in line:
                   f.write(line)

    def sync(self):
       for _, repo in self.system.settings.repositories.items():
           repo.sync()