
import __builtin__

import contextlib
import mock
import os.path
import simplejson
import testify as T
import urllib2

from jar_downloader.jar_downloader_base import Jar
import jar_downloader.vanilla_jar_downloader
from jar_downloader.vanilla_jar_downloader import get_versions_json
from jar_downloader.vanilla_jar_downloader import InvalidVersionFileError
from jar_downloader.vanilla_jar_downloader import LATEST_FILE
from jar_downloader.vanilla_jar_downloader import VanillaJarDownloader
from jar_downloader.vanilla_jar_downloader import VERSIONS_ENDPOINT

class TestGetVersionsJson(T.TestCase):
    """Tests the get_versions_json method."""

    def test_get_versions_json(self):
        with contextlib.nested(
            mock.patch.object(simplejson, 'loads', autospec=True),
            mock.patch.object(urllib2, 'urlopen', autospec=True),
        ) as (
            loads_mock,
            urlopen_mock,
        ):
            retval = get_versions_json()
            urlopen_mock.assert_called_once_with(VERSIONS_ENDPOINT)
            loads_mock.assert_called_once_with(
                urlopen_mock.return_value.read.return_value
            )
            T.assert_equal(retval, loads_mock.return_value)

    @T.suite('integration')
    @T.suite('external')
    def test_structure_of_external_json(self):
        """A smoke test of the json data returned from the version service."""
        json_object = get_versions_json()

        T.assert_equal(
            json_object,
            {
                'versions': mock.ANY, # Tested more explicitly below
                'latest': {
                    'release': mock.ANY,
                    'snapshot': mock.ANY,
                }
            }
        )

        # Versions should be a list of dict objects
        T.assert_isinstance(json_object['versions'], list)
        for version_dict in json_object['versions']:
            T.assert_equal(
                version_dict,
                {
                    'releaseTime': mock.ANY,
                    'type': mock.ANY,
                    'id': mock.ANY,
                    'time': mock.ANY,
                }
            )

class TestVanillaJarDownloader(T.TestCase):
    """Tests the vanilla jar downloader."""

    directory = str(object())
    server_file = 'minecraft_server.%s.jar'

    class FakeFile(object):
        def __init__(self, contents):
            self.contents = contents

        def read(self):
            return self.contents

        def __enter__(self): return self
        def __exit__(self, *args): pass

    @T.setup_teardown
    def patch_out_base_init_verifying_directory(self):
        """Patch out JarDownloaderBase.__init__ beacuse it asserts that the
        path we are using exists.
        """

        def fake_init(fakeself, jar_directory):
            """A fake init method to bypass os.path.exists check."""
            fakeself.jar_directory = jar_directory

        with mock.patch.object(
            jar_downloader.vanilla_jar_downloader.JarDownloaderBase,
            '__init__',
            fake_init,
        ):
            yield

    def test_latest_filename(self):
        T.assert_equal(
            VanillaJarDownloader(self.directory)._latest_filename,
            os.path.join(self.directory, LATEST_FILE)
        )

    def test_to_jar(self):
        version = str(object())
        filename = self.server_file % version
        jar_out = VanillaJarDownloader._to_jar(filename)

        T.assert_isinstance(jar_out, Jar)
        T.assert_equal(jar_out.filename, filename)
        T.assert_equal(jar_out.short_version, version)

    def test_download_versions(self):
        with mock.patch.object(os, 'listdir', autospec=True) as listdir_mock:
            listdir_mock.return_value = [
                # Some garbage
                'foo.txt',
                'foo.jar',
                'foo',
                # Some actual files that we downloaded
                self.server_file % 'herp',
                self.server_file % 'derp',
                self.server_file % '1.6.2',
            ]
            instance = VanillaJarDownloader(self.directory)
            downloaded_versions = instance.downloaded_versions
            T.assert_equal(
                downloaded_versions,
                [
                    Jar(self.server_file % 'herp', 'herp'),
                    Jar(self.server_file % 'derp', 'derp'),
                    Jar(self.server_file % '1.6.2', '1.6.2'),
                ]
            )

    def test_try_to_get_latest_version_file_does_not_exist(self):
        with contextlib.nested(
            mock.patch.object(os.path, 'exists', autospec=True),
            T.assert_raises(InvalidVersionFileError),
        ) as (
            exists_mock,
            _
        ):
            exists_mock.return_value = False
            VanillaJarDownloader(self.directory)._try_to_get_latest_version()

    def test_try_to_get_latest_version_jar_does_not_exists(self):
        def fake_exists(path):
            """Returns true every other time."""
            fake_exists.return_value = not fake_exists.return_value
            return fake_exists.return_value

        # Return True the first time, note it returns the opposite of what it
        # says it does
        fake_exists.return_value = False

        with contextlib.nested(
            mock.patch.object(__builtin__, 'open', autospec=True),
            mock.patch.object(os.path, 'exists', fake_exists),
            T.assert_raises(InvalidVersionFileError),
        ) as (
            open_mock,
            _,
            _,
        ):
            open_mock.return_value = self.FakeFile(' foo ')
            VanillaJarDownloader(self.directory)._try_to_get_latest_version()

    def test_try_to_get_latest_version_jar_exists(self):
        with contextlib.nested(
            mock.patch.object(os.path, 'exists', autospec=True),
            mock.patch.object(__builtin__, 'open', autospec=True),
        ) as (
            exists_mock,
            open_mock,
        ):
            exists_mock.return_value = True
            open_mock.return_value = self.FakeFile('   foo   \n')
            instance = VanillaJarDownloader(self.directory)
            latest_version = instance._try_to_get_latest_version()
            T.assert_equal(
                latest_version,
                open_mock.return_value.contents.strip(),
            )

    def test_latest_download_version(self):
        with mock.patch.object(
            VanillaJarDownloader,
            '_try_to_get_latest_version',
            autospec=True,
        ) as _try_to_get_latest_mock:
            _try_to_get_latest_mock.return_value = self.server_file % 'herp'
            instance = VanillaJarDownloader(self.directory)
            return_value = instance.latest_downloaded_version
            T.assert_equal(return_value, Jar(self.server_file % 'herp', 'herp'))

    def test_latest_download_version_trys_to_clean_up_on_failure(self):
        with contextlib.nested(
            mock.patch.object(
                VanillaJarDownloader,
                '_try_to_get_latest_version',
                autospec=True,
            ),
            mock.patch.object(os.path, 'exists', autospec=True),
            mock.patch.object(os, 'remove', autospec=True),
        ) as (
            _try_to_get_latest_mock,
            exists_mock,
            remove_mock,
        ):
            _try_to_get_latest_mock.side_effect = InvalidVersionFileError
            exists_mock.return_value = True
            instance = VanillaJarDownloader(self.directory)
            with T.assert_raises(InvalidVersionFileError):
                instance.latest_downloaded_version

            # Make sure we attempted to delete the file
            exists_mock.assert_called_once_with(instance._latest_filename)
            remove_mock.assert_called_once_with(instance._latest_filename)

