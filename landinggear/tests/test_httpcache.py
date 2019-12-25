from __future__ import absolute_import, print_function

import os.path
from unittest import TestCase

from pip_shims import USER_CACHE_DIR

from landinggear.base import LandingGearError
from landinggear.httpcache import HTTPCacheExtractor
from landinggear.tests.helpers import tempcache, tempdir


class TestHTTPCache(TestCase):
    def test_default_pip_cache(self):
        """
        If no pip cache is provided, the default is used.
        """
        extractor = HTTPCacheExtractor()
        self.assertEqual(
            extractor.http_cache_dir, os.path.join(USER_CACHE_DIR, "http"))

    def test_missing_pip_cache(self):
        """
        A missing pip cache dir throws an error.
        """
        with tempdir() as basedir:
            pip_cache_dir = os.path.join(basedir, "pipcache")
            self.assertRaises(
                LandingGearError, HTTPCacheExtractor, pip_cache_dir)

    def test_missing_http_cache(self):
        """
        A pip cache dir with no http cache returns no packages.
        """
        with tempdir() as basedir:
            pip_cache_dir = os.path.join(basedir, "pipcache")
            os.mkdir(pip_cache_dir)
            extractor = HTTPCacheExtractor(pip_cache_dir)
            self.assertEqual(list(extractor.iter_cache()), [])

    def test_empty_http_cache(self):
        """
        A pip cache dir with an empty http cache returns no packages.
        """
        with tempcache() as pipcache:
            extractor = HTTPCacheExtractor(pipcache.path)
            self.assertEqual(list(extractor.iter_cache()), [])

    def test_pip_cache_with_zip(self):
        """
        A pip wheel cache with wheels in it returns some packages.
        """
        with tempcache() as pipcache:
            sdist1 = pipcache.write_sdist("ab/cd/ef/ghij/foo.zip")
            extractor = HTTPCacheExtractor(pipcache.path)
            self.assertEqual(
                sorted([cw.filepath for cw in extractor.iter_cache()]),
                sorted([sdist1])
            )

    def test_pip_cache_with_wheels(self):
        """
        A pip wheel cache with wheels in it returns some packages.
        """
        with tempcache() as pipcache:
            wheel1 = pipcache.write_sdist("ab/cd/ef/ghij/foo.whl")
            wheel2 = pipcache.write_sdist("12/34/56/7890/bar.whl")
            extractor = HTTPCacheExtractor(pipcache.path)
            self.assertEqual(
                sorted([cw.filepath for cw in extractor.iter_cache()]),
                sorted([wheel1, wheel2]),
            )

    def test_zip_content(self):
        """
        An sdist may be a valid zip file.
        """
        with tempcache() as pipcache:
            zf = pipcache.write_test_zip("wheels/test-1.0.zip")
            extractor = HTTPCacheExtractor(pipcache.path)
            pipcache.write_cache_entry(extractor, zf, "ab/cd/ef/ghij/klmn")
            files = list(extractor.iter_cache())
            self.assertEqual(len(files), 1)
            cached_zip = files[0]
            self.assertEqual(cached_zip.can_symlink, False)
            self.assertEqual(cached_zip.is_package, True)
            self.assertEqual(cached_zip.package_filename, "test-1.0.zip")
            self.assertTrue(cached_zip.get_package_data().startswith(b"PK"))

    def test_wheel_content(self):
        """
        Any file is inspected to check it is a valid wheel.
        """
        with tempcache() as pipcache:
            wheel = pipcache.write_test_wheel("py2-none-any")
            extractor = HTTPCacheExtractor(pipcache.path)
            pipcache.write_cache_entry(extractor, wheel, "ab/cd/ef/ghij/klmn")
            wheels = list(extractor.iter_cache())
            self.assertEqual(len(wheels), 1)
            cached_wheel = wheels[0]
            self.assertEqual(cached_wheel.can_symlink, False)
            self.assertEqual(cached_wheel.is_package, True)
            self.assertEqual(
                cached_wheel.package_filename, "test-1.0-py2-none-any.whl")
            self.assertTrue(cached_wheel.get_package_data().startswith(b"PK"))

    def test_wheel_invalid_content(self):
        """
        Any file ending with .whl is not automatically a valid wheel or zip.
        """
        with tempcache() as pipcache:
            pipcache.write_http("ab/cd/ef/ghij/foo.whl", b"round")
            extractor = HTTPCacheExtractor(pipcache.path)
            [cached_wheel] = extractor.iter_cache()
            self.assertEqual(cached_wheel.can_symlink, False)
            self.assertEqual(cached_wheel.is_package, False)
            self.assertIsNone(cached_wheel.package_filename)
            self.assertIsNone(cached_wheel.get_package_data())
