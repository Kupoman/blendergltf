import argparse
import difflib
import filecmp
import os
import subprocess
import shutil
import sys

BASE_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(BASE_DIR, 'sources')
EXPECT_DIR = os.path.join(BASE_DIR, 'expect')
OUT_DIR = os.path.join(BASE_DIR, 'test-out')
CONFIGS = [
    [],
    ['interleaved']
]

def export_files(out_dir):
    sources = [f for f in os.listdir(SOURCE_DIR) if f != 'textures']
    for source in sources:
        in_name = os.path.join(SOURCE_DIR, source)
        command = [
            'blender',
            in_name,
            '--background',
            '-noaudio',
            '--python',
            os.path.join(BASE_DIR, 'export.py'),
            '--',
            out_dir,
        ]
        for config in CONFIGS:
            subprocess.run(command + config)


def update():
    export_files(EXPECT_DIR)
    sys.exit(0)


def prepare_out_dir():
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.mkdir(OUT_DIR)


def get_diff(name):
    expect_file = os.path.join(EXPECT_DIR, name)
    test_file = os.path.join(OUT_DIR, name)
    with open(expect_file) as fin:
        expect_lines = fin.readlines()
    with open(test_file) as fin:
        test_lines = fin.readlines()
    for line in difflib.unified_diff(expect_lines, test_lines):
        print(line)


def check():
    prepare_out_dir()
    export_files(OUT_DIR)
    names = os.listdir(OUT_DIR)
    _, failures, errors = filecmp.cmpfiles(OUT_DIR, EXPECT_DIR, names, shallow=False)
    if errors:
        print('Unable to diff the following files:', errors)
        sys.exit(1)

    for failure in failures:
        print('Difference found in ', failure, ':')
        print(get_diff(failure))
    if failures:
        sys.exit(1)
    print('All files passed')
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser('Interact with integration test files.')
    parser.add_argument(
        'command',
        choices=['check', 'update'],
        help='command to execute on test files'
    )
    args = parser.parse_args()
    globals()[args.command]()


if __name__ == '__main__':
    main()
