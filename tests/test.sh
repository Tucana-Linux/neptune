#!/bin/bash
REPO="http://192.168.1.143:88"
# DO NOT CHANGE
TEMP_DIR="$PWD/temp"
LOG_DIR="$TEMP_DIR/logs"
REPO_DIR="$TEMP_DIR/repo"
CHROOT="$TEMP_DIR/chroot"
RED='\033[0;31m' 
GREEN='\033[0;32m' 
NC='\033[0m'
sudo mercury-install yq python-build python-installer
mkdir -p $TEMP_DIR $REPO_DIR $CHROOT $LOG_DIR
# Universal Function
function chroot_setup() {
    # Using mercury for now, later it will use the system version of neptune-bootstrap
    # taken from tucana-autobuild

  if [[ -d $CHROOT/dev ]]; then
     umount $CHROOT/dev/pts
     umount $CHROOT/dev
     umount $CHROOT/proc
     umount $CHROOT/sys
     rm -rf $TEMP_DIR
     mkdir -p $TEMP_DIR $REPO_DIR $CHROOT $LOG_DIR
  fi
  sleep 3  
  # Subset of the installer script, check there for explanations
  cd $TEMP_DIR || exit
  git clone https://github.com/xXTeraXx/Tucana.git
  # Change Install path and Repo
  sed -i "s|INSTALL_PATH=.*|INSTALL_PATH=$CHROOT|g" Tucana/mercury/mercury-install
  sed -i "s|INSTALL_PATH=.*|INSTALL_PATH=$CHROOT|g" Tucana/mercury/mercury-sync
  sed -i "s|REPO=.*|REPO=$REPO|g" Tucana/mercury/mercury-install
  sed -i "s|REPO=.*|REPO=$REPO|g" Tucana/mercury/mercury-sync
  
  # Install the base system
  cd Tucana/mercury || exit
  ./mercury-sync
  printf "y\n" | ./mercury-install base
  
  # Mount temp filesystems
  mount --bind /dev $CHROOT/dev
  mount --bind /proc $CHROOT/proc
  mount --bind /sys $CHROOT/sys
  mount --bind /dev/pts $CHROOT/dev/pts

  # Setup Systemd services (probably not needed)
  chroot $CHROOT /bin/bash -c "systemd-machine-id-setup && systemctl preset-all"
  
  # SSL and shadow first time setup
   # DNS
  echo "nameserver 1.1.1.1" > $CHROOT/etc/resolv.conf
  chroot $CHROOT /bin/bash -c "make-ca -g --force"
  chroot $CHROOT /bin/bash -c "pwconv"
  
  # Locale
  echo "Building Locales"
  echo "en_US.UTF-8 UTF-8" > $CHROOT/etc/locale.gen
  chroot $CHROOT /bin/bash -c "locale-gen"

  # TODO Change to /var/lib/neptune once neptune is finalized Rahul Chandra <rahul@tucanalinux.org>
  mkdir -p $CHROOT/var/cache/mercury/file-lists
  chroot $CHROOT /bin/bash -c "mercury-install --y python-urllib3 python-requests pyyaml"
}

function setup() {
  mkdir -p $REPO_DIR/{packages,depend,available-packages}
  cd $TEMP_DIR
  cd ..
  python3 -m build --wheel --skip-dependency-check
  if ! python3 -m installer --destdir=$CHROOT  dist/*.whl; then
    echo "SETUP FAILED!"
    exit 1
  fi
  mkdir -p $CHROOT/etc/neptune
  cat > $CHROOT/etc/neptune/config.yaml << "EOF"
repositories:
  - "http://127.0.0.1:99"

system-settings:
  install_path: "/"
  yes_mode_by_default: false
  stream_chunk_size: 8192  
EOF
  cd $REPO_DIR
  screen -dmS repo python3 -m http.server 99
  cd -
}

function make_mock_package() {
  local pkgname="$1"
  local depends="$2"
  local use_postinst="$3"
  local backup="$4"

  cd $TEMP_DIR || exit
  mkdir -p "$pkgname"/tests/"$pkgname"
  # Looks weird but essentialy just to make sure that file operations are working throughout
  date=$(date)
  echo "$pkgname $date" > "$pkgname"/tests/"$pkgname"/"$pkgname"
  echo "$depends" > $REPO_DIR/depend/depend-$pkgname
  cd $REPO_DIR/depend/ || exit
  tar -cvzpf depends.tar.xz *
  cd - || exit
  if [[ $use_postinst == "true" ]]; then
    cat > "$pkgname"/postinst << EOF
echo "This is a postinstall test"
touch /tests/$pkgname/postinst-success
EOF
  fi

  if [[ $backup != "" ]]; then
    echo "option1=original" > "$pkgname"/tests/"$pkgname"/config.yaml
    echo "/tests/$pkgname/config.yaml" > $pkgname/backup
  fi

  tar -cvzpf "$pkgname".tar.xz "$pkgname"
  rm -rf "$pkgname"
  mv "$pkgname".tar.xz $REPO_DIR/packages/

  cd $REPO_DIR/packages || exit
  ls | sed 's/.tar.xz//g' > ../available-packages/packages
  sha256sum * > ../available-packages/sha256
  cd - || exit
}

function p_or_f() {
  local name=$1
  local result=$2
  if [[ $result == "0" ]]; then
    echo -e "Test $name: ${GREEN}OK${NC}" 
  else 
    echo -e "Test $name: ${RED}FAILED${NC}" 
    exit 1
  fi
}
# Test Functions
function config_test() {
  echo "Running configuration test..."
  make_mock_package "test-package" "" "" ""

  local config_path="$CHROOT/etc/neptune/config.yaml"

  if [[ ! -f $config_path ]]; then
    echo "Configuration file does not exist at $config_path"
    return 1
  fi

  # Backup the original configuration file
  cp $config_path "${config_path}.bak"

  # Test: Modify repository URL
  echo "Testing repository URL..."
  yq eval ".repositories[0] = \"invalid_url\"" -i $config_path
  chroot $CHROOT /bin/bash -c "neptune sync" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune sync succeeded with invalid repository URL, which should not happen"
    cp "${config_path}.bak" $config_path
    return 1
  fi

  # Restore the repository URL for subsequent tests
  yq eval ".repositories[0] = \"$REPO\"" -i $config_path

  # Test: Modify install path
  echo "Testing install path..."
  yq eval ".system-settings.install_path = \"/invalid/path\"" -i $config_path
  chroot $CHROOT /bin/bash -c "neptune install --y test-package" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune install succeeded with invalid install path, which should not happen"
    cp "${config_path}.bak" $config_path
    return 1
  fi

  # Restore the install path for subsequent tests
  yq eval ".system-settings.install_path = \"$CHROOT\"" -i $config_path

  # Test: Modify yes_mode_by_default
  # This test is repeated during arguments
  cp "${config_path}.bak" $config_path
  chroot $CHROOT /bin/bash -c "neptune sync"
  echo "Testing yes_mode_by_default..."
  yq eval ".system-settings.yes_mode_by_default = true" -i $config_path
  chroot $CHROOT /bin/bash -c "neptune install test-package" >/dev/null 2>&1 &
  sleep 5
  if [[ ! -f $CHROOT/tests/test-package/test-package ]]; then
    echo "yes_mode_by_default FAILED"
    cp "${config_path}.bak" $config_path
    return 1
  fi

  # Restore the original configuration
  mv "${config_path}.bak" $config_path

  echo "Configuration test passed"
  return 0

}

function arguments_test() {
  echo "Running arguments test..."
  make_mock_package "arguments-test" "" "" ""
  
  chroot $CHROOT /bin/bash -c "neptune sync" >/dev/null 2>&1
  # Test: Install without arguments
  echo "Testing 'neptune install' without arguments..."
  chroot $CHROOT /bin/bash -c "neptune install" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune install succeeded without arguments, which should not happen"
    return 1
  fi

  # Test: Install with --y but no package
  echo "Testing 'neptune install --y' without specifying a package..."
  chroot $CHROOT /bin/bash -c "neptune install --y" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune install succeeded with --y but no package, which should not happen"
    return 1
  fi

  # Test: Install with a valid package and --y
  echo "Testing 'neptune install --y arguments-test'..."
  make_mock_package "arguments-test" "" "" ""
  chroot $CHROOT /bin/bash -c "neptune sync" >/dev/null
  sleep 5
  chroot $CHROOT /bin/bash -c "neptune install arguments-test" &
  if [[ ! -f $CHROOT/tests/arguments-test/arguments-test ]]; then
    echo "Neptune install failed with a valid package and --y"
    return 1
  fi

  # Test: Install with a valid package without --y
  # it will proceeed if all packages are installed so we need a new one if the last one worked
  make_mock_package "arguments-test-2" "" "" ""
  chroot $CHROOT /bin/bash -c "neptune sync"

  echo "Testing 'neptune install with yes_mode set to false without --y, should not proceed'..."
  yq eval ".system-settings.yes_mode_by_default = false" -i $CHROOT/etc/neptune/config.yaml
  sleep 5
  chroot $CHROOT /bin/bash -c "neptune install arguments-test-2" &
  if [[ -f $CHROOT/tests/arguments-test-2/arguments-test-2 ]]; then
    echo "Neptune install proceeded without --y when yes_mode_by_default is false"
    return 1
  fi

  # Test: Install with an invalid package
  echo "Testing 'neptune install --y invalid-package'..."
  chroot $CHROOT /bin/bash -c "neptune install --y invalid-package" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune install succeeded with an invalid package"
    return 1
  fi

  echo "Arguments test passed"
  return 0

}

function sync_test() {
  # todo fix this Rahul Chandra <rahul@tucanalinux.org>
  echo "Running sync test"
  # need to do this to init the repo
  make_mock_package "sync-test" "" "" ""

  chroot $CHROOT /bin/bash -c "neptune sync"
  local result=$?
  if [[ $result -ne 0 ]]; then
    echo "Neptune sync failed with code $result"
    return 1
  fi

  # Validate that the files were fetched and extracted
  if [[ ! -f $CHROOT/var/cache/mercury/available-packages ]]; then
    echo "Available packages file not downloaded"
    return 1
  fi
  if [[ ! -d $CHROOT/var/cache/mercury/depend ]]; then
    echo "Dependency files not extracted"
    return 1
  fi

  echo "Sync test passed"
  return 0
}
#function bootstrap_test() {}
function install_test_no_depends() {
  make_mock_package "install-test" "" "" ""

  chroot $CHROOT /bin/bash -c "neptune sync"
  # test non existent package first
  if ! chroot $CHROOT /bin/bash -c "neptune install --y this-does-not-exist" | grep "not found"; then
    echo "Install attempted to install a non-existent package"
    return 1
  fi
  
  chroot $CHROOT /bin/bash -c "neptune install --y install-test"
  if [[ $? != 0 ]]; then
    echo "Neptune exited with error code $?"
    return 1
  fi
  if [ ! -f $CHROOT/tests/install-test/install-test ]; then
    echo "Installation did not install the proper files"
    return 1
  fi
  if [ ! -f $CHROOT/var/cache/mercury/file-lists/install-test.list ]; then
    echo "Installation did not install the file list"
    return 1
  fi
  if ! cat $CHROOT/etc/installed_package | grep install-test; then
    echo "Package not in installed_package"
    return 1
  fi
  if ! cat $CHROOT/etc/wanted_packages | grep install-test; then
    echo "Package not in wanted_packages"
    return 1
  fi
  echo "Tests passed"
  return 0
}
function install_test_with_depends() {
  # TODO Test circular dependency resolution Rahul Chandra <rahul@tucanalinux.org>
  make_mock_package "libtest" "" "" ""
  make_mock_package "install-test-depend" "libtest" "" ""

  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y install-test-depend"
  if [[ $? != 0 ]]; then
    echo "Neptune exited with error code $?"
    return 1
  fi
  if ! cat $CHROOT/etc/installed_package | grep libtest; then
    echo "Depend not in installed_package"
    return 1
  fi
  if cat $CHROOT/etc/wanted_packages | grep libtest; then
    echo "Depend is wrongly in wanted_packages"
    return 1
  fi
  echo "Tests passed"
  return 0

}

function install_test_with_postinst() {
  make_mock_package "install-test-postinst" "" "true" ""
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y install-test-postinst"
  
  if [[ $? != 0 ]]; then
    echo "Neptune exited with error code $?"
    return 1
  fi
  if [ ! -f $CHROOT/tests/install-test-postinst/postinst-success ]; then
    echo "Post install was meant to create a file that is not on the disk"
    return 1
  fi
  return 0
}

function reinstall_test() {
  # If this test passes than we know that file io while the file is open is already working
     # Create a script to keep the file open
    cat > $TEMP_DIR/keep_file_open.py << EOF
import time
import sys

# Open the file and keep it open
with open('$CHROOT/tests/install-test/install-test', 'r') as f:
    print("File opened. Waiting...")
    sys.stdout.flush()
    
    # Wait for a long time to simulate an active file
    time.sleep(60)
EOF

    # Run file-keeping script in background
    python3 /tmp/keep_file_open.py &
    KEEP_FILE_PID=$!

    # Wait a moment to ensure file is opened
    sleep 2

    # Attempt to reinstall while file is open
    neptune reinstall open-file-test

    # Check if reinstall succeeded
    if [[ $? == 0 ]]; then
        echo "Reinstall succeeded with open file"
        kill $KEEP_FILE_PID
        return 0
    else
        echo "Reinstall could not write the file"
        kill $KEEP_FILE_PID
        return 1
    fi
}

function update_test() {
  # This is probably the most complicated one here so let me explain it
  # Packages: update-test-root, libupdate, libupdatenew
  # update-test-root is the root package, it will have a config file that will need to be backed up and initally depend on libupdate
  # libupdate is going to be the inital dependency of update-test-root
  # at this point update-test-root will be installed
  # update-test-root will be changed in the repo, new sha256sum, and it will have it's dependencies changed to libupdatenew
  # config file will be changed so that option1=new, sha256sum will be recorded
  # neptune update will run
  # in order for the test to pass it must
  # 1) update the files in update-test-root to a new version WITHOUT changing the config file
  # 2) remove libupdate
  # 3) Install libupdatenew
  # 4) Not error

  make_mock_package "update-test-root" "libupdate" "" "1"
  make_mock_package "libupdate" "" "" ""
  make_mock_package "libupdatenew" "" "" ""

  chroot $CHROOT /bin/bash -c "neptune install --y update-test-root"
  if [[ $? != 0 ]]; then
    echo "Test failed: Could not install package"
    return 1
  fi
  # We don't need to retest whether the depend was installed or not because that should've already been tested
  make_mock_package "update-test-root" "libupdatenew" "" ""
  echo "option 1=new" > $CHROOT/test/update-test-root/config.yaml
  CONFIG_HASH=$(sha256sum $CHROOT/test/update-test-root/config.yaml)
  FILE_HASH=$(sha256sum $CHROOT/test/update-test-root/update-test-root)
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune update --y"
  if [[ $? != 0 ]]; then
    echo "Test failed: neptune update exited with non-zero code"
    return 1
  fi
  CONFIG_HASH_2=$(sha256sum $CHROOT/test/update-test-root/config.yaml)
  FILE_HASH_2=$(sha256sum $CHROOT/test/update-test-root/update-test-root)
  
  if [[ $FILE_HASH_2 == "$FILE_HASH" ]]; then
    echo "Test failed: Did not update file"
    return 1;
  fi

  if [[ $CONFIG_HASH_2 != "$CONFIG_HASH" ]]; then
    echo "Test failed: Config file was modified"
    return 1;
  fi

  if [ -f  /tests/libupdate/libupdate ]; then
    echo "Test failed: Dependency not removed"
    return 1;
  fi

  if [ ! -f  /tests/libupdatenew/libupdatenew ]; then
    echo "Test failed: New dependency not installed"
    return 1;
  fi

}
function remove_test() {
  # Create mock packages to test removal
  make_mock_package "remove-test-depend" "" "" ""
  make_mock_package "remove-test" "remove-test-depend" "" ""

  # Sync the package list and install the mock packages
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y remove-test"

  # Attempt to remove the installed packages
  chroot $CHROOT /bin/bash -c "neptune remove --y install-test"
  if [[ $? != 0 ]]; then
    echo "Test failed: neptune remove ended with a non-zero status code"
  fi


  # Check if files from the packages were removed
  if [ -f "$CHROOT/tests/remove-test/remove-test" ]; then
    echo "Test failed: install-test files still present after removal"
    return 1
  fi

  if [ -f "$CHROOT/tests/remove-test-depend/remove-test-depend" ]; then
    echo "Test failed: remove-test-depend files still present after removal"
    return 1
  fi
  
  # Check if installed package has been updated
  if cat $CHROOT/etc/installed_package | grep "remove-test"; then
    echo "Test failed: remove-test is still listed in installed_package after removal"
    return 1
  fi

  if cat $CHROOT/etc/installed_package | grep "install-test-depend"; then
    echo "Test failed: remove-test-depend is still listed in installed_package after removal"
    return 1
  fi

  if cat $CHROOT/etc/wanted_packages | grep "remove-test"; then
    echo "Test failed: remove-test is still listed in wanted_packages after removal"
    return 1
  fi

  echo "remove_test passed successfully"
  return 0


}
function run_test() {
  local test_function=$1
  local test_name=$2
  cd $LOG_DIR
  $test_function >> "$test_name.log" 2>&1
  p_or_f "$test_name" "$?"
}
function run_tests() {
  # these are synchronous, meaning that if one fails the next one is likely to also fail, so it exits if any test fails
  chroot_setup
  setup
  run_test sync_test "Neptune Sync"
  run_test install_test_no_depends "Neptune Install Without Depends"
  run_test install_test_with_depends "Neptune Install with Depends"
  run_test install_test_with_postinst "Neptune Postinstall"
  run_test config_test "Neptune Config Check"
  run_test arguments_test "Neptune Arugments Check"
  run_test reinstall_test "Neptune Reinstall"
  run_test remove_test "Neptune Remove"
  run_test update_test "Neptune Update"
}
run_tests