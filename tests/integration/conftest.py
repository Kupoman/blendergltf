import os
import shutil

import pytest


BASE_DIR = os.path.dirname(__file__)
OUT_DIR = os.path.join(BASE_DIR, 'test-out')
@pytest.fixture(scope='session')
def prepare_out_dir():
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.mkdir(OUT_DIR)


def pytest_addoption(parser):
    parser.addoption(
        '--update',
        action='store_true',
        help='Update expect files with current results'
    )


@pytest.fixture
def update(request):
    return request.config.getoption("--update")
