import itertools
import os
import subprocess

import pytest


FILES = [
    'meshes',
    'shape_keys',
    'character',
    'large_mesh',
]
CONFIGS = [
    '',
    'interleaved'
]
TESTS = itertools.product(FILES, CONFIGS)


BASE_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(BASE_DIR, 'sources')
EXPECT_DIR = os.path.join(BASE_DIR, 'expect')
OUT_DIR = os.path.join(BASE_DIR, 'test-out')


def export_file(out_dir, file_name, config):
    in_name = os.path.join(SOURCE_DIR, file_name + '.blend')
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
    options = config.split(' ') if config else []
    subprocess.run(command + options)


def compare_files(name):
    expect_file = os.path.join(EXPECT_DIR, name + '.gltf')
    test_file = os.path.join(OUT_DIR, name + '.gltf')
    with open(expect_file) as fin:
        expect_string = fin.read()
    with open(test_file) as fin:
        test_string = fin.read()
    assert expect_string == test_string

@pytest.mark.parametrize('file_name,config', TESTS)
def test_integration(update, prepare_out_dir, file_name, config):
    if update:
        export_file(EXPECT_DIR, file_name, config)
    else:
        export_file(OUT_DIR, file_name, config)
        compare_files(file_name)
