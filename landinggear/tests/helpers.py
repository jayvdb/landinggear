from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
from contextlib import contextmanager
from email.generator import Generator
from email.message import Message
from io import StringIO
from shutil import rmtree
from tempfile import mkdtemp
from zipfile import ZipFile

from landinggear.httpcache import FakeRequest


@contextmanager
def tempdir(suffix="", prefix="tmp", dir=None):
    tmpdir_path = mkdtemp(suffix, prefix, dir)
    try:
        yield tmpdir_path
    finally:
        rmtree(tmpdir_path)


@contextmanager
def tempcache():
    with tempdir() as basedir:
        yield TempPipCache(os.path.join(basedir, "pipcache"))


class FakeResponse(object):
    def __init__(self, headers=None):
        self.headers = headers
        if self.headers is None:
            self.headers = {}
        self.status = 200
        self.version = 2
        self.reason = None
        self.strict = True
        self.decode_content = False


def generate_WHEEL_file(tag):
    # Cheat to avoid email.message unicode problems
    if sys.version_info[0] == 2:
        # "".__class__ is equivalent of `unicode`
        tag = "".__class__(tag)
        content = "Tag: {}".format(tag)
        return content.encode()

    msg = Message()
    msg["Wheel-Version"] = "1.0"  # of the spec
    msg["Generator"] = "test helper (0.1)"
    msg["Root-Is-Purelib"] = "true"
    msg["Tag"] = tag
    s = StringIO()
    Generator(s, maxheaderlen=0).flatten(msg)
    return s.getvalue().encode()


class TempPipCache(object):
    def __init__(self, pip_cache_dir):
        self.path = pip_cache_dir
        os.mkdir(self.path)
        os.mkdir(self.join("http"))
        os.mkdir(self.join("wheels"))

    def join(self, *pathbits):
        return os.path.join(self.path, *pathbits)

    def write_file(self, filepath, content=b""):
        fullpath = self.join(*filepath.split("/"))
        os.makedirs(os.path.dirname(fullpath))
        with open(fullpath, "wb") as f:
            f.write(content)
        return os.path.realpath(fullpath)

    def write_wheel(self, filepath, content=b""):
        return self.write_file("wheels/" + filepath, content)

    def write_test_wheel(self, tag):
        fullpath = self.join("wheels/test-1.0-{}.whl".format(tag))

        with ZipFile(fullpath, "w") as wf:
            wf.writestr("hello/hello.py", b'print("Hello, world!")\n')
            wf.writestr("test-1.0.dist-info/WHEEL", generate_WHEEL_file(tag))

        return os.path.realpath(fullpath)

    def write_test_zip(self, filepath):
        fullpath = self.join(*filepath.split("/"))
        base = os.path.dirname(fullpath)
        if not os.path.exists(base):
            os.makedirs(base)

        with ZipFile(fullpath, "w") as zf:
            zf.writestr("test-1.0/hello.py", b'print("Hello, world!")\n')

        return os.path.realpath(fullpath)

    def write_cache_entry(self, extractor, input_filename, cachepath):
        content = open(input_filename, "rb").read()
        raw = extractor.serializer.dumps(
            FakeRequest(), FakeResponse(), body=content)
        self.write_http(cachepath, raw)

    def write_http(self, filepath, content=b""):
        return self.write_file("http/" + filepath, content)

    def write_sdist(self, filepath, content=b""):
        return self.write_file("http/" + filepath, content)
