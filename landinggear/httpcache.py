from __future__ import absolute_import, print_function

import os
import os.path
from zipfile import BadZipfile, ZipFile
from tarfile import TarError, open as tarfile_open

from cachecontrol import CacheControlAdapter
from pip_shims import SafeFileCache
from wheel.pkginfo import read_pkg_info_bytes

from landinggear.base import (
    CachedPackage,
    CacheExtractor,
    LandingGearError,
    pip_cache_subdir,
)

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO  # noqa


class HTTPCacheExtractor(CacheExtractor):
    """
    Extracts tarballs and wheels from the HTTP cache.
    """

    def __init__(self, pip_cache_dir=None):
        self.http_cache_dir = pip_cache_subdir("http", pip_cache_dir)
        if pip_cache_dir is not None and not os.path.isdir(pip_cache_dir):
            raise LandingGearError("Missing pip cache: %s" % (pip_cache_dir,))
        self.adapter = CacheControlAdapter(SafeFileCache(self.http_cache_dir))
        self.serializer = self.adapter.controller.serializer

    def iter_cache(self):
        for root, dirs, files in os.walk(self.adapter.cache.directory):
            for file in files:
                yield CachedResponse(os.path.join(root, file), self.serializer)


class CachedResponse(CachedPackage):
    def __init__(self, filepath, serializer):
        self.filepath = filepath
        self.serializer = serializer
        self.resp_data = self.get_resp_data()

    def get_package_filename(self):
        return self.get_zip_filename() or self.get_tarball_filename()

    def get_package_data(self):
        return self.get_resp_data()

    def get_resp_data(self):
        with open(self.filepath, "rb") as f:
            cached_data = f.read()
        resp = self.serializer.loads(
            FakeRequest(), cached_data)
        if resp is not None:
            return resp.read(decode_content=True)
        return None

    def get_tarball_filename(self):
        for compression in ["gz", "bz2", "xz"]:
            try:
                tarfile = tarfile_open(
                    mode="r:" + compression, fileobj=BytesIO(self.resp_data)
                )
                break
            except TarError:
                pass
        else:
            # The response was not a tarball
            return None
        try:
            first_entry = tarfile.next()
        except TarError:
            # The tarball was empty
            return None
        path = first_entry.name.rsplit("/")[0]
        return "{}.tar.{}".format(path, compression)

    def get_wheel_filename(self):
        filename = self.get_zip_filename()
        if filename.endswith(".whl"):
            return filename

    def get_zip_filename(self):
        try:
            zipfile = ZipFile(BytesIO(self.resp_data))
        except BadZipfile:
            # The response was not a zipfile and therefore not a wheel.
            return None
        first_dir = None
        for zipinfo in zipfile.infolist():
            dirname, filename = os.path.split(zipinfo.filename)
            if filename == "WHEEL" and dirname.endswith(".dist-info"):
                if os.path.dirname(dirname):
                    # This isn't a top-level dir, so we don't want it.
                    continue
                return "%s-%s.whl" % (
                    dirname[:-len(".dist-info")],
                    self._collect_tags(zipfile.read(zipinfo)))
            if not first_dir:
                first_dir = dirname
        return "{}.zip".format(first_dir)

    def _collect_tags(self, wheel_metadata):
        pyver, abi, plat = set(), set(), set()
        pkginfo = read_pkg_info_bytes(wheel_metadata)
        tags = pkginfo.get_all("tag")
        for tag in tags:
            t_pyver, t_abi, t_plat = tag.split("-")
            pyver.add(t_pyver)
            abi.add(t_abi)
            plat.add(t_plat)
        return "%s-%s-%s" % tuple([
            ".".join(sorted(tag)) for tag in (pyver, abi, plat)])


class FakeRequest(object):
    def __init__(self, headers=None):
        self.headers = headers
        if self.headers is None:
            self.headers = {"Accept-Encoding": "gzip, deflate"}
