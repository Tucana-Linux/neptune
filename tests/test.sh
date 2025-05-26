#!/bin/bash
# TODO Version Normalizer Test
# TODO Config settings test for loglevels
# TODO Bootstrap test
REPO="http://192.168.1.143:88"
# DO NOT CHANGE
TEMP_DIR="$HOME/neptune-tests"
LOG_DIR="$TEMP_DIR/logs"
GIT_LOCATION="/home/rahul/Git-Clones/neptune-0.1.3/"
REPO_DIR="$TEMP_DIR/repo"
REPO2_DIR="$TEMP_DIR/repo2"
CHROOT="$TEMP_DIR/chroot"
RED='\033[0;31m' 
GREEN='\033[0;32m' 
NC='\033[0m'
sudo neptune install yq python-build python-installer screen
mkdir -p $TEMP_DIR $REPO_DIR $REPO2_DIR $CHROOT $LOG_DIR
# Universal Function


function cleanup() {
  echo "Cleaning up..."
  screen -X -S repo quit || true 
  screen -X -S repo2 quit || true
  rm -rf "$REPO_DIR" "$REPO2_DIR"
}

trap cleanup EXIT

function chroot_setup() {

  if [[ -d $CHROOT/dev ]]; then
     umount $CHROOT/dev/pts
     umount $CHROOT/dev
     umount $CHROOT/proc
     umount $CHROOT/sys
     rm -rf $TEMP_DIR
     mkdir -p $TEMP_DIR $REPO_DIR $REPO2_DIR $CHROOT $LOG_DIR
  fi
  sleep 3  
  # Subset of the installer script, check there for explanations
  cd $TEMP_DIR || exit

  
  neptune-bootstrap $CHROOT --y
  sed -i "s@\"http.*\"@\"${REPO}\"@" $CHROOT/etc/neptune/config.yaml
  
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
  chroot $CHROOT /bin/bash -c "neptune install --y python-packaging"


}

function setup() {
  mkdir -p $REPO_DIR/{packages,depend,available-packages}
  mkdir -p $REPO2_DIR/{packages,depend,available-packages}
  touch $REPO_DIR/available-packages/packages.yaml
  touch $REPO2_DIR/available-packages/packages.yaml
  cd $GIT_LOCATION
  python3 -m build --wheel --skip-dependency-check
  if ! python3 -m installer --destdir=$CHROOT/neptune-test dist/*.whl; then
    echo "SETUP FAILED!"
    exit 1
  fi
  cp -rpv $CHROOT/neptune-test/* $CHROOT
  mkdir -p $CHROOT/etc/neptune
  # Wipe installed_package and wanted_packages it doesn't interfere
  rm -f $CHROOT/var/lib/neptune/installed_package
  rm -f $CHROOT/var/lib/neptune/wanted_packages
  touch $CHROOT/var/lib/neptune/installed_package
  touch $CHROOT/var/lib/neptune/wanted_packages
  touch $CHROOT/var/lib/neptune/system-packages.yaml
  cat > $CHROOT/etc/neptune/config.yaml << "EOF"
system-settings:
  install_path: "/"
  yes_mode_by_default: false
  stream_chunk_size: 8192
  loglevel: 10
EOF
cat > $CHROOT/etc/neptune/repositories.yaml << "EOF"
repositories:
  repo1:
    url: "http://127.0.0.1:99/"
  repo2:
    url: "http://127.0.0.1:98/"
EOF
  cd $REPO_DIR
  screen -dmS repo python3 -m http.server 99
  cd $REPO2_DIR
  screen -dmS repo2 python3 -m http.server 98
  cd $GIT_LOCATION
}

function make_mock_package() {
  local pkgname="$1"
  local depends="$2"
  local use_postinst="$3"
  local backup="$4"
  local repo="$5"
  local version="$6"

  cd $TEMP_DIR || exit
  mkdir -p "$pkgname"/tests/"$pkgname"
  # Looks weird but essentially just to make sure that file operations are working throughout
  date=$(date +%s)
  echo "$pkgname $date" > "$pkgname"/tests/"$pkgname"/"$pkgname"
  # symlink for testing
  ln -sfv /tests/"$pkgname"/"$pkgname" "$pkgname"/tests/"$pkgname"/"$pkgname"-sym

  if [[ $repo != "1" && $repo != "2" ]]; then
    echo "TEST ERROR, REPO not defined for package $pkgname"
    exit 1
  fi

  if [[ $use_postinst == "true" ]]; then
    cat > "$pkgname"/postinst << EOF
echo "This is a postinstall test"
touch /tests/$pkgname/postinst-success
EOF
  fi

  if [[ $backup == "1" ]]; then
    echo "BACKUP IS GOING"
    echo "option1=original" > "$pkgname"/tests/"$pkgname"/config.yaml
    echo "/tests/$pkgname/config.yaml" > $pkgname/backup
  fi
  echo "$version" > "$pkgname"/tests/"$pkgname"/version

  tar -cvzpf "$pkgname".tar.xz "$pkgname"
  rm -rf "$pkgname"
  if [[ $repo == "1" ]]; then
    mv "$pkgname".tar.xz $REPO_DIR/packages/
    cd $REPO_DIR/packages/ || exit
  elif [[ $repo == "2" ]]; then
    mv "$pkgname".tar.xz $REPO2_DIR/packages/
    cd $REPO2_DIR/packages/ || exit
  fi
  if [[ $repo == "1" ]]; then
    cd $REPO_DIR/packages || exit
  fi

  if [[ $repo == "2" ]]; then
    cd $REPO2_DIR/packages || exit
  fi
  if [ -s ../available-packages/packages.yaml ] && grep -q '[^[:space:]]' ../available-packages/packages.yaml; then
    yq -i 'del(.[strenv(pkgname)])' ../available-packages/packages.yaml
  fi
  python3 $GIT_LOCATION/tests/env-to-yaml.py "$pkgname" "$depends" "$version" "100" "100" "$date" >> ../available-packages/packages.yaml



  cd $TEMP_DIR || exit
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
  # TODO Test new config options
  echo "Running configuration test..."
  make_mock_package "test-package" "" "" "" "1" "1.0.0"

  local config_path="$CHROOT/etc/neptune/config.yaml"

  if [[ ! -f $config_path ]]; then
    echo "Configuration file does not exist at $config_path"
    return 1
  fi

  # Backup the original configuration file
  cp $config_path "${config_path}.bak"

  # Test: Modify repository URL
  echo "Testing repository URL..."
  yq eval ".repositories.repo1.url = \"http://invalid.url\"" -i "$config_path"
  chroot $CHROOT /bin/bash -c "neptune sync" >/dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    echo "Neptune sync succeeded with invalid repository URL, which should not happen"
    cp "${config_path}.bak" $config_path
    return 1
  fi

  # Restore the repository URL for subsequent tests
  yq eval ".repositories.repo1.url = \"$REPO\"" -i "$config_path"

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
  make_mock_package "arguments-test" "" "" "" "1" "1.0.0"
  
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
  make_mock_package "arguments-test" "" "" "" "1" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync" >/dev/null
  chroot $CHROOT /bin/bash -c "neptune install --y arguments-test" &
  sleep 5
  if [[ ! -f $CHROOT/tests/arguments-test/arguments-test ]]; then
    echo "Neptune install failed with a valid package and --y"
    return 1
  fi

  # Test: Install with a valid package without --y
  # it will proceeed if all packages are installed so we need a new one if the last one worked
  make_mock_package "arguments-test-2" "" "" "" "1" "1.0.0"
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
  make_mock_package "sync-test" "" "" "" "1" "1.0.0"
  make_mock_package "sync-test" "" "" "" "2" "1.0.0"

  chroot $CHROOT /bin/bash -c "neptune sync"
  local result=$?
  if [[ $result -ne 0 ]]; then
    echo "Neptune sync failed with code $result"
    return 1
  fi

  # Validate that the files were fetched and extracted
  IFS=" "
  for num in $(echo "1 2"); do
    if [[ ! -f $CHROOT/var/lib/neptune/cache/repos/repo$num/packages.yaml ]]; then
      echo "Packages meta file for repo$num not downloaded"
      return 1
    fi
  done
  IFS=$' \t\n'
  echo "Sync test passed"
  return 0
}
function install_test_no_depends() {
  make_mock_package "install-test" "" "" "" "1" "1.2.5"

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
  if [ ! -L $CHROOT/tests/install-test/install-test-sym ]; then
    echo "Installation did not perserve or install symlink"
    return 1
  fi
  if [ ! -f $CHROOT/var/lib/neptune/file-lists/install-test.list ]; then
    echo "Installation did not install the file list"
    return 1
  fi
  if ! cat $CHROOT/var/lib/neptune/system-packages.yaml | grep install-test; then
    echo "Package not in system-packages yaml"
    return 1
  fi
  if ! cat $CHROOT/var/lib/neptune/system-packages.yaml | grep "1.2.5"; then
    echo "Package version not registered properly"
    return 1
  fi
  wanted_status=$(yq '.install-test.wanted' $CHROOT/var/lib/neptune/system-packages.yaml)
  if [[ "$wanted_status" == "null" || -z "$wanted_status" ]]; then
    echo "Package not set as wanted"
    return 1
  fi

  echo "Tests passed"
  return 0
}

function install_test_with_depends() {
  # TODO Test circular dependency resolution Rahul Chandra <rahul@tucanalinux.org>
  make_mock_package "libtest" "" "" "" "1" "1.0.0"
  make_mock_package "install-test-depend" "libtest" "" "" "1" "1.0.0"

  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y install-test-depend"
  if [[ $? != 0 ]]; then
    echo "Neptune exited with error code $?"
    return 1
  fi
  if ! cat $CHROOT/var/lib/neptune/system-packages.yaml | grep libtest; then
    echo "Depend not registered in system-packages.yaml"
    return 1
  fi
  wanted_status=$(yq '.libtest.wanted' $CHROOT/var/lib/neptune/system-packages.yaml)
  if [[ $wanted_status == "true" ]]; then
    echo "Depend is wrongly registered as wanted"
    return 1
  fi
  make_mock_package "install-test-depend" "libtest" "" "" "1" "1.0.1"
  chroot $CHROOT /bin/bash -c "neptune install --y install-test-depend"
  if cat $CHROOT/tests/install-test-depend/version | grep "1.0.1"; then
    echo "Install attempted to install an already installed package"
    return 1
  fi
  echo "Tests passed"
  return 0

}

function install_test_with_postinst() {
  make_mock_package "install-test-postinst" "" "true" "" "1" "1.0.0"
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
  make_mock_package "reinstall-test" "" "" "" "1" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y reinstall-test"

     # Create a script to keep the file open
    cat > $CHROOT/keep_file_open.py << EOF
import time
import sys

# Open the file and keep it open
with open('/tests/reinstall-test/reinstall-test', 'r') as f:
    print("File opened. Waiting...")
    sys.stdout.flush()
    
    # Wait for a long time to simulate an active file
    time.sleep(60)
EOF

    # Run file-keeping script in background
    chroot $CHROOT /bin/bash -c "python3 /keep_file_open.py" &
    KEEP_FILE_PID=$!

    # Wait a moment to ensure file is opened
    sleep 2

    # Attempt to reinstall while file is open
    chroot $CHROOT /bin/bash -c "neptune reinstall --y reinstall-test"

    # Check if reinstall succeeded
    if [[ $? == 0 ]]; then
        echo "Reinstall succeeded with open file"
        kill $KEEP_FILE_PID
    else
        echo "Reinstall could not write the file"
        kill $KEEP_FILE_PID
        return 1
    fi

    # Make sure it won't attempt to reinstall something that is not installed
    if ! chroot $CHROOT /bin/bash -c "neptune reinstall --y reinstall-test-2" | grep "not installed"; then
      echo "Reinstall attempted to reinstall a package that is not installed"
      return 1
    fi
    return 0
    
}

function multi_repo_test() {
  # install package that is in repo 2 but not 1 
  make_mock_package "multi-repo-2" "" "" "" "2" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y multi-repo-2"
  if [[ ! -f $CHROOT/tests/multi-repo-2/version ]]; then
    echo "TEST FAILED: Package from repo-2 files not installed"
    return 1
  fi

  # update
  make_mock_package "multi-repo" "" "" "" "1" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y multi-repo"
  make_mock_package "multi-repo" "" "" "" "2" "1.0.1"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune update --y"
  if ! cat $CHROOT/tests/multi-repo/version | grep -E '1\.0\.1'; then
    echo "TEST FAILED: Updating from a package in repo-2 failed"
    return 1
  fi

  # depends from other repo
  make_mock_package "multi-repo-depend" "" "" "" "2" "1.0.0"
  make_mock_package "multi-repo-main" "multi-repo-depend" "" "" "1" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y multi-repo-main"

  if [[ ! -f $CHROOT/tests/multi-repo-depend/version ]]; then
    echo "TEST FAILED: Cross-repo dependencies test failed"
    return 1
  fi

  # 1 repo down but the other up
  make_mock_package "multi-repo-down-test" "" "" "" "1" "1.0.0"
  make_mock_package "multi-repo-down-test-2" "" "" "" "2" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"

  # change repo url
  cat > $CHROOT/etc/neptune/repositories.yaml << "EOF"
repositories:
  repo1:
    url: "http://127.0.0.1:99/"
  repo2:
    url: "http://127.0.0.1:97/"
EOF
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y multi-repo-down-test-2"
  if [[ $? -eq 0 ]]; then
    echo "TEST FAILED: Neptune install suceeded with package from a repo that is down"
  fi
  chroot $CHROOT /bin/bash -c "neptune install --y multi-repo-down-test"
  if [[ ! -f $CHROOT/tests/multi-repo-down-test/version ]]; then
    echo "TEST FAILED: One repo being unavailable caused all repos to be unavailable"
    return 1
  fi

  echo "Test multi-repo PASSED"
  return 0
}

function update_test() {
  # This is probably the most complicated one here so here's an explanation
  # Packages: update-test-root, libupdate, libupdatenew
  # update-test-root is the root package, it will have a config file that will need to be backed up and initally depend on libupdate
  # libupdate is going to be the inital dependency of update-test-root
  # at this point update-test-root will be installed
  # update-test-root will be changed in the repo, new sha256sum and version, and it will have it's dependencies changed to libupdatenew
  # config file will be changed so that option1=new, sha256sum will be recorded
  # neptune update will run
  # in order for the test to pass it must
  # 1) update the files in update-test-root to a new version WITHOUT changing the config file
  # 2) remove libupdate
  # 3) Install libupdatenew
  # 4) Not error
  # This does not test multi-repo support

  make_mock_package "update-test-root" "libupdate" "" "" "1" "1.0.0"
  make_mock_package "libupdate" "" "" "" "1" "1.0.0"
  make_mock_package "libupdatenew" "" "" "" "1" "1.0.0"
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y update-test-root"
  if [[ $? != 0 ]]; then
    echo "Test failed: Could not install package"
    return 1
  fi
  echo "Package installed"
  # We don't need to retest whether the depend was installed or not because that should've already been tested
  # sleep so that it has a new date
  sleep 4
  make_mock_package "update-test-root" "libupdatenew" "" "1" "1" "1.0.1"
  echo "option 1=new" > $CHROOT/tests/update-test-root/config.yaml
  CONFIG_HASH=$(sha256sum $CHROOT/tests/update-test-root/config.yaml)
  FILE_HASH=$(sha256sum $CHROOT/tests/update-test-root/update-test-root)
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune update --y"
  if [[ $? != 0 ]]; then
    echo "Test failed: neptune update exited with non-zero code"
    return 1
  fi
  CONFIG_HASH_2=$(sha256sum $CHROOT/tests/update-test-root/config.yaml)
  FILE_HASH_2=$(sha256sum $CHROOT/tests/update-test-root/update-test-root)
  
  if [[ $FILE_HASH_2 == "$FILE_HASH" ]]; then
    echo "Test failed: Did not update file"
    return 1
  fi

  if [[ $CONFIG_HASH_2 != "$CONFIG_HASH" ]]; then
    echo "Test failed: Config file was modified"
    return 1
  fi

  if [ -f $CHROOT/tests/libupdate/libupdate ]; then
    echo "Test failed: Dependency not removed"
    return 1
  fi

  if [ ! -f $CHROOT/tests/libupdatenew/libupdatenew ] || ! cat $CHROOT/var/lib/neptune/system-packages.yaml | grep "libupdatenew"; then
    echo "Test failed: New dependency not installed"
    return 1
  fi



  version_status=$(yq '.update-test-root.version' $CHROOT/var/lib/neptune/system-packages.yaml)
  if [[ $version_status != "1.0.1" ]]; then
    echo "The system-packages.yaml version was not updated or is otherwise broken"
    return 1
  fi

  echo "Update test passed"

  return 0

}
function remove_test() {
  # Create mock packages to test removal
  make_mock_package "remove-test-depend" "" "" "" "1" "1.0.0"
  make_mock_package "remove-test" "remove-test-depend" "" "" "1" "1.0.0"

  # Sync the package list and install the mock packages
  chroot $CHROOT /bin/bash -c "neptune sync"
  chroot $CHROOT /bin/bash -c "neptune install --y remove-test"

  # Attempt to remove the installed packages
  chroot $CHROOT /bin/bash -c "neptune remove --y remove-test"
  if [[ $? != 0 ]]; then
    echo "Test failed: neptune remove ended with a non-zero status code"
  fi


  # Check if files from the packages were removed
  if [ -f "$CHROOT/tests/remove-test/remove-test" ]; then
    echo "Test failed: remove-test files still present after removal"
    return 1
  fi

  if [ -f "$CHROOT/tests/remove-test-depend/remove-test-depend" ]; then
    echo "Test failed: remove-test-depend files still present after removal"
    return 1
  fi

  if [ -L "$CHROOT/tests/remove-test-depend/remove-test-depend-sym" ]; then
    echo "Test failed: remove-test-depend symlink still present after removal"
    return 1
  fi
  
  # Check if installed package has been updated
  if cat $CHROOT/var/lib/neptune/system-packages.yaml | grep "remove-test"; then
    echo "Test failed: remove-test is still listed in system-packages.yaml after removal"
    return 1
  fi

  if cat $CHROOT/var/lib/neptune/system-packages.yaml | grep "remove-test-depend"; then
    echo "Test failed: remove-test-depend is still listed in system-packages.yaml after removal"
    return 1
  fi

  echo "remove_test passed successfully"
  return 0
}

function bootstrap_test() {
  # Reset back to tucanalinux.org
  cat > $CHROOT/etc/neptune/repositories.yaml << EOF
repositories:
  tucana-mainline:
    url: "$REPO"
EOF
  chroot $CHROOT /bin/bash -c "neptune sync"
  
  chroot $CHROOT /bin/bash -c "mkdir -p /bootstrap"
  if ! chroot $CHROOT /bin/bash -c "neptune-bootstrap /bootstrap --y"; then
    echo "BOOTSTRAP TEST FAILED, Bootstrap exited with non-zero status code"
    return 1
  fi

  if ! chroot $CHROOT/bootstrap /bin/bash -c "exit 0"; then
    echo "Bootstrap chroot non-functional"
    return 1
  fi
  if [ ! -f $CHROOT/bootstrap/var/lib/neptune/system-packages.yaml ]; then
    echo "Main system-packages.yaml file doesn't exist"
    return 1
  fi

  wanted_status=$(yq '.base.wanted' $CHROOT/bootstrap/var/lib/neptune/system-packages.yaml)

  if [[ $wanted_status != "true" ]]; then
    echo "base not set as wanted"
    return 1
  fi
  version_status=$(yq '.base.version' $CHROOT/bootstrap/var/lib/neptune/system-packages.yaml)

  if [[ $version_status == "null" ]]; then
    echo "Package not set properly in bootstrap"
    return 1
  fi

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
  # TODO Update for multi-repo
  # run_test config_test "Neptune Config Check"
  run_test arguments_test "Neptune Arugments Check"
  run_test reinstall_test "Neptune Reinstall"
  run_test remove_test "Neptune Remove"
  run_test update_test "Neptune Update"
  run_test multi_repo_test "Neptune Multi-Repo Support"
  run_test bootstrap_test "Neptune Bootstrap Test"
  echo "All Tests Passed"
}
run_tests
