#! /usr/bin/env bash

echo -e "\nInstalling snapcraft & multipass\n"
snap install snapcraft
snap install multipass

echo -e "\nRemoving old builds\n"
rm -rf dotrun_*.snap

echo -e "\nBuilding dotrun\n"
snapcraft

echo -e "\nInstalling built snap\n"
snap install --dangerous --devmode dotrun_*.snap
