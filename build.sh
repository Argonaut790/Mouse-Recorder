#!/bin/bash

echo "Cleaning previous builds..."
rm -rf build dist

echo "Building executable..."
pyinstaller --clean recorder.spec

echo "Done!"
