""" test_apt_source
Testing various config variations of the apt_source custom config
"""
import glob
import os
import re
import shutil
import socket
import tempfile

from unittest import TestCase

import mock
from mock import call

from curtin import util
from curtin import gpg
from curtin.commands import apt_config


EXPECTEDKEY = u"""-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1

mI0ESuZLUgEEAKkqq3idtFP7g9hzOu1a8+v8ImawQN4TrvlygfScMU1TIS1eC7UQ
NUA8Qqgr9iUaGnejb0VciqftLrU9D6WYHSKz+EITefgdyJ6SoQxjoJdsCpJ7o9Jy
8PQnpRttiFm4qHu6BVnKnBNxw/z3ST9YMqW5kbMQpfxbGe+obRox59NpABEBAAG0
HUxhdW5jaHBhZCBQUEEgZm9yIFNjb3R0IE1vc2VyiLYEEwECACAFAkrmS1ICGwMG
CwkIBwMCBBUCCAMEFgIDAQIeAQIXgAAKCRAGILvPA2g/d3aEA/9tVjc10HOZwV29
OatVuTeERjjrIbxflO586GLA8cp0C9RQCwgod/R+cKYdQcHjbqVcP0HqxveLg0RZ
FJpWLmWKamwkABErwQLGlM/Hwhjfade8VvEQutH5/0JgKHmzRsoqfR+LMO6OS+Sm
S0ORP6HXET3+jC8BMG4tBWCTK/XEZw==
=ACB2
-----END PGP PUBLIC KEY BLOCK-----"""

ADD_APT_REPO_MATCH = r"^[\w-]+:\w"

TARGET = "/"


def load_tfile(filename):
    """ load_tfile
    load file and return content after decoding
    """
    try:
        content = util.load_file(filename, mode="r")
    except Exception as error:
        print('failed to load file content for test: %s' % error)
        raise

    return content


class PseudoRunInChroot(object):
    def __init__(self, args, **kwargs):
        print("HEY: %s" % ' '.join(args))
        if len(args) > 0:
            self.target = args[0]
        else:
            self.target = kwargs.get('target')

    def __call__(self, args, **kwargs):
        if self.target != "/":
            chroot = ["chroot", self.target]
        else:
            chroot = []
        return util.subp(chroot + args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return

RunInChrootStr = "curtin.commands.apt_config.util.RunInChroot"


class TestAptSourceConfig(TestCase):
    """ TestAptSourceConfig
    Main Class to test apt configs
    """
    def setUp(self):
        super(TestAptSourceConfig, self).setUp()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.aptlistfile = os.path.join(self.tmp, "single-deb.list")
        self.aptlistfile2 = os.path.join(self.tmp, "single-deb2.list")
        self.aptlistfile3 = os.path.join(self.tmp, "single-deb3.list")
        self.join = os.path.join
        self.matcher = re.compile(ADD_APT_REPO_MATCH).search

    @staticmethod
    def _add_apt_sources(*args, **kwargs):
        with mock.patch.object(util, 'apt_update'):
            apt_config.add_apt_sources(*args, **kwargs)

    @staticmethod
    def _get_default_params():
        """ get_default_params
        Get the most basic default mrror and release info to be used in tests
        """
        params = {}
        params['RELEASE'] = util.lsb_release()['codename']
        arch = util.get_architecture()
        params['MIRROR'] = apt_config.get_default_mirrors(arch)["PRIMARY"]
        return params

    def _myjoin(self, *args, **kwargs):
        """ _myjoin - redir into writable tmpdir"""
        if (args[0] == "/etc/apt/sources.list.d/" and
                args[1] == "cloud_config_sources.list" and
                len(args) == 2):
            return self.join(self.tmp, args[0].lstrip("/"), args[1])
        else:
            return self.join(*args, **kwargs)

    def _apt_src_basic(self, filename, cfg):
        """ _apt_src_basic
        Test Fix deb source string, has to overwrite mirror conf in params
        """
        params = self._get_default_params()

        self._add_apt_sources(cfg, TARGET, template_params=params,
                              aa_repo_match=self.matcher)

        self.assertTrue(os.path.isfile(filename))

        contents = load_tfile(filename)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", "http://test.ubuntu.com/ubuntu",
                                   "karmic-backports",
                                   "main universe multiverse restricted"),
                                  contents, flags=re.IGNORECASE))

    def test_apt_src_basic(self):
        """test_apt_src_basic - Test fix deb source string"""
        cfg = {self.aptlistfile: {'source':
                                  ('deb http://test.ubuntu.com/ubuntu'
                                   ' karmic-backports'
                                   ' main universe multiverse restricted')}}
        self._apt_src_basic(self.aptlistfile, cfg)

    def test_apt_src_basic_tri(self):
        """test_apt_src_basic_tri - Test multiple fix deb source strings"""
        cfg = {self.aptlistfile: {'source':
                                  ('deb http://test.ubuntu.com/ubuntu'
                                   ' karmic-backports'
                                   ' main universe multiverse restricted')},
               self.aptlistfile2: {'source':
                                   ('deb http://test.ubuntu.com/ubuntu'
                                    ' precise-backports'
                                    ' main universe multiverse restricted')},
               self.aptlistfile3: {'source':
                                   ('deb http://test.ubuntu.com/ubuntu'
                                    ' lucid-backports'
                                    ' main universe multiverse restricted')}}
        self._apt_src_basic(self.aptlistfile, cfg)

        # extra verify on two extra files of this test
        contents = load_tfile(self.aptlistfile2)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", "http://test.ubuntu.com/ubuntu",
                                   "precise-backports",
                                   "main universe multiverse restricted"),
                                  contents, flags=re.IGNORECASE))
        contents = load_tfile(self.aptlistfile3)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", "http://test.ubuntu.com/ubuntu",
                                   "lucid-backports",
                                   "main universe multiverse restricted"),
                                  contents, flags=re.IGNORECASE))

    def _apt_src_replacement(self, filename, cfg):
        """ apt_src_replace
        Test Autoreplacement of MIRROR and RELEASE in source specs
        """
        params = self._get_default_params()
        self._add_apt_sources(cfg, TARGET, template_params=params,
                              aa_repo_match=self.matcher)

        self.assertTrue(os.path.isfile(filename))

        contents = load_tfile(filename)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", params['MIRROR'], params['RELEASE'],
                                   "multiverse"),
                                  contents, flags=re.IGNORECASE))

    def test_apt_src_replace(self):
        """test_apt_src_replace - Test Autoreplacement of MIRROR and RELEASE"""
        cfg = {self.aptlistfile: {'source': 'deb $MIRROR $RELEASE multiverse'}}
        self._apt_src_replacement(self.aptlistfile, cfg)

    def test_apt_src_replace_fn(self):
        """test_apt_src_replace_fn - Test filename being overwritten in dict"""
        cfg = {'ignored': {'source': 'deb $MIRROR $RELEASE multiverse',
                           'filename': self.aptlistfile}}
        # second file should overwrite the dict key
        self._apt_src_replacement(self.aptlistfile, cfg)

    def _apt_src_replace_tri(self, cfg):
        """ _apt_src_replace_tri
        Test three autoreplacements of MIRROR and RELEASE in source specs with
        generic part
        """
        self._apt_src_replacement(self.aptlistfile, cfg)

        # extra verify on two extra files of this test
        params = self._get_default_params()
        contents = load_tfile(self.aptlistfile2)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", params['MIRROR'], params['RELEASE'],
                                   "main"),
                                  contents, flags=re.IGNORECASE))
        contents = load_tfile(self.aptlistfile3)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb", params['MIRROR'], params['RELEASE'],
                                   "universe"),
                                  contents, flags=re.IGNORECASE))

    def test_apt_src_replace_tri(self):
        """test_apt_src_replace_tri - Test multiple replacements/overwrites"""
        cfg = {self.aptlistfile: {'source': 'deb $MIRROR $RELEASE multiverse'},
               'notused':        {'source': 'deb $MIRROR $RELEASE main',
                                  'filename': self.aptlistfile2},
               self.aptlistfile3: {'source': 'deb $MIRROR $RELEASE universe'}}
        self._apt_src_replace_tri(cfg)

    def _apt_src_keyid(self, filename, cfg, keynum):
        """ _apt_src_keyid
        Test specification of a source + keyid
        """
        params = self._get_default_params()

        with mock.patch.object(util, 'subp',
                               return_value=('fakekey 1234', '')) as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)

        # check if it added the right ammount of keys
        calls = []
        for _ in range(keynum):
            calls.append(call(['apt-key', 'add', '-'], data=b'fakekey 1234'))
        mockobj.assert_has_calls(calls, any_order=True)

        self.assertTrue(os.path.isfile(filename))

        contents = load_tfile(filename)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb",
                                   ('http://ppa.launchpad.net/smoser/'
                                    'cloud-init-test/ubuntu'),
                                   "xenial", "main"),
                                  contents, flags=re.IGNORECASE))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_keyid(self):
        """test_apt_src_keyid - Test source + keyid with filename being set"""
        cfg = {self.aptlistfile: {'source': ('deb '
                                             'http://ppa.launchpad.net/'
                                             'smoser/cloud-init-test/ubuntu'
                                             ' xenial main'),
                                  'keyid': "03683F77"}}
        self._apt_src_keyid(self.aptlistfile, cfg, 1)

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_keyid_tri(self):
        """test_apt_src_keyid_tri - Test multiple src+keyid+filen overwrites"""
        cfg = {self.aptlistfile:  {'source': ('deb '
                                              'http://ppa.launchpad.net/'
                                              'smoser/cloud-init-test/ubuntu'
                                              ' xenial main'),
                                   'keyid': "03683F77"},
               'ignored':         {'source': ('deb '
                                              'http://ppa.launchpad.net/'
                                              'smoser/cloud-init-test/ubuntu'
                                              ' xenial universe'),
                                   'keyid': "03683F77",
                                   'filename': self.aptlistfile2},
               self.aptlistfile3: {'source': ('deb '
                                              'http://ppa.launchpad.net/'
                                              'smoser/cloud-init-test/ubuntu'
                                              ' xenial multiverse'),
                                   'keyid': "03683F77"}}

        self._apt_src_keyid(self.aptlistfile, cfg, 3)
        contents = load_tfile(self.aptlistfile2)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb",
                                   ('http://ppa.launchpad.net/smoser/'
                                    'cloud-init-test/ubuntu'),
                                   "xenial", "universe"),
                                  contents, flags=re.IGNORECASE))
        contents = load_tfile(self.aptlistfile3)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb",
                                   ('http://ppa.launchpad.net/smoser/'
                                    'cloud-init-test/ubuntu'),
                                   "xenial", "multiverse"),
                                  contents, flags=re.IGNORECASE))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_key(self):
        """test_apt_src_key - Test source + key"""
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'source': ('deb '
                                             'http://ppa.launchpad.net/'
                                             'smoser/cloud-init-test/ubuntu'
                                             ' xenial main'),
                                  'key': "fakekey 4321"}}

        with mock.patch.object(util, 'subp') as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)

        mockobj.assert_any_call(['apt-key', 'add', '-'], data=b'fakekey 4321')

        self.assertTrue(os.path.isfile(self.aptlistfile))

        contents = load_tfile(self.aptlistfile)
        self.assertTrue(re.search(r"%s %s %s %s\n" %
                                  ("deb",
                                   ('http://ppa.launchpad.net/smoser/'
                                    'cloud-init-test/ubuntu'),
                                   "xenial", "main"),
                                  contents, flags=re.IGNORECASE))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_keyonly(self):
        """test_apt_src_keyonly - Test key without source"""
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'key': "fakekey 4242"}}

        with mock.patch.object(util, 'subp') as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)

        mockobj.assert_any_call(['apt-key', 'add', '-'], data=b'fakekey 4242')

        # filename should be ignored on key only
        self.assertFalse(os.path.isfile(self.aptlistfile))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_keyidonly(self):
        """test_apt_src_keyidonly - Test keyid without source"""
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'keyid': "03683F77"}}

        with mock.patch.object(util, 'subp',
                               return_value=('fakekey 1212', '')) as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)

        mockobj.assert_any_call(['apt-key', 'add', '-'], data=b'fakekey 1212')

        # filename should be ignored on key only
        self.assertFalse(os.path.isfile(self.aptlistfile))

    def apt_src_keyid_real(self, cfg, expectedkey):
        """apt_src_keyid_real
        Test specification of a keyid without source including
        up to addition of the key (add_apt_key_raw mocked to keep the
        environment as is)
        """
        params = self._get_default_params()

        with mock.patch.object(apt_config, 'add_apt_key_raw') as mockkey:
            with mock.patch.object(gpg, 'getkeybyid',
                                   return_value=expectedkey) as mockgetkey:
                self._add_apt_sources(cfg, TARGET, template_params=params,
                                      aa_repo_match=self.matcher)

        keycfg = cfg[self.aptlistfile]
        mockgetkey.assert_called_with(keycfg['keyid'],
                                      keycfg.get('keyserver',
                                                 'keyserver.ubuntu.com'))
        mockkey.assert_called_with(expectedkey, TARGET)

        # filename should be ignored on key only
        self.assertFalse(os.path.isfile(self.aptlistfile))

    def test_apt_src_keyid_real(self):
        """test_apt_src_keyid_real - Test keyid including key add"""
        keyid = "03683F77"
        cfg = {self.aptlistfile: {'keyid': keyid}}

        self.apt_src_keyid_real(cfg, EXPECTEDKEY)

    def test_apt_src_longkeyid_real(self):
        """test_apt_src_longkeyid_real Test long keyid including key add"""
        keyid = "B59D 5F15 97A5 04B7 E230  6DCA 0620 BBCF 0368 3F77"
        cfg = {self.aptlistfile: {'keyid': keyid}}

        self.apt_src_keyid_real(cfg, EXPECTEDKEY)

    def test_apt_src_longkeyid_ks_real(self):
        """test_apt_src_longkeyid_ks_real Test long keyid from other ks"""
        keyid = "B59D 5F15 97A5 04B7 E230  6DCA 0620 BBCF 0368 3F77"
        cfg = {self.aptlistfile: {'keyid': keyid,
                                  'keyserver': 'keys.gnupg.net'}}

        self.apt_src_keyid_real(cfg, EXPECTEDKEY)

    def test_apt_src_keyid_keyserver(self):
        """test_apt_src_keyid_keyserver - Test custom keyserver"""
        keyid = "03683F77"
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'keyid': keyid,
                                  'keyserver': 'test.random.com'}}

        # in some test environments only *.ubuntu.com is reachable
        # so mock the call and check if the config got there
        with mock.patch.object(gpg, 'getkeybyid',
                               return_value="fakekey") as mockgetkey:
            with mock.patch.object(apt_config, 'add_apt_key_raw') as mockadd:
                self._add_apt_sources(cfg, TARGET, template_params=params,
                                      aa_repo_match=self.matcher)

        mockgetkey.assert_called_with('03683F77', 'test.random.com')
        mockadd.assert_called_with('fakekey', TARGET)

        # filename should be ignored on key only
        self.assertFalse(os.path.isfile(self.aptlistfile))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_ppa(self):
        """test_apt_src_ppa - Test specification of a ppa"""
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'source': 'ppa:smoser/cloud-init-test'}}

        with mock.patch.object(util, 'subp') as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)
        mockobj.assert_any_call(['add-apt-repository',
                                 'ppa:smoser/cloud-init-test'])

        # adding ppa should ignore filename (uses add-apt-repository)
        self.assertFalse(os.path.isfile(self.aptlistfile))

    @mock.patch(RunInChrootStr, new=PseudoRunInChroot)
    def test_apt_src_ppa_tri(self):
        """test_apt_src_ppa_tri - Test specification of multiple ppa's"""
        params = self._get_default_params()
        cfg = {self.aptlistfile: {'source': 'ppa:smoser/cloud-init-test'},
               self.aptlistfile2: {'source': 'ppa:smoser/cloud-init-test2'},
               self.aptlistfile3: {'source': 'ppa:smoser/cloud-init-test3'}}

        with mock.patch.object(util, 'subp') as mockobj:
            self._add_apt_sources(cfg, TARGET, template_params=params,
                                  aa_repo_match=self.matcher)
        calls = [call(['add-apt-repository', 'ppa:smoser/cloud-init-test']),
                 call(['add-apt-repository', 'ppa:smoser/cloud-init-test2']),
                 call(['add-apt-repository', 'ppa:smoser/cloud-init-test3'])]
        mockobj.assert_has_calls(calls, any_order=True)

        # adding ppa should ignore all filenames (uses add-apt-repository)
        self.assertFalse(os.path.isfile(self.aptlistfile))
        self.assertFalse(os.path.isfile(self.aptlistfile2))
        self.assertFalse(os.path.isfile(self.aptlistfile3))

    def test_mir_apt_list_rename(self):
        """test_mir_apt_list_rename - Test find mirror and apt list renaming"""
        pre = "/var/lib/apt/lists"
        # filenames are archive dependent
        arch = util.get_architecture()
        if arch in apt_config.PRIMARY_ARCHES:
            component = "ubuntu"
            archive = "archive.ubuntu.com"
        else:
            component = "ubuntu-ports"
            archive = "ports.ubuntu.com"

        cfg = {'primary': [{'arches': ["default"],
                            'uri':
                            'http://test.ubuntu.com/%s/' % component}],
               'security': [{'arches': ["default"],
                             'uri':
                             'http://testsec.ubuntu.com/%s/' % component}]}
        post = ("%s_dists_%s-updates_InRelease" %
                (component, util.lsb_release()['codename']))
        fromfn = ("%s/%s_%s" % (pre, archive, post))
        tofn = ("%s/test.ubuntu.com_%s" % (pre, post))

        mirrors = apt_config.find_apt_mirror_info(cfg)

        self.assertEqual(mirrors['MIRROR'],
                         "http://test.ubuntu.com/%s/" % component)
        self.assertEqual(mirrors['PRIMARY'],
                         "http://test.ubuntu.com/%s/" % component)
        self.assertEqual(mirrors['SECURITY'],
                         "http://testsec.ubuntu.com/%s/" % component)

        # get_architecture would fail inside the unittest context
        with mock.patch.object(util, 'get_architecture', return_value=arch):
            with mock.patch.object(os, 'rename') as mockren:
                with mock.patch.object(glob, 'glob',
                                       return_value=[fromfn]):
                    apt_config.rename_apt_lists(mirrors, TARGET)

        mockren.assert_any_call(fromfn, tofn)

    @mock.patch("curtin.commands.apt_config.util.get_architecture")
    def test_mir_apt_list_rename_non_slash(self, m_get_architecture):
        target = os.path.join(self.tmp, "rename_non_slash")
        apt_lists_d = os.path.join(target, "./" + apt_config.APT_LISTS)

        m_get_architecture.return_value = 'amd64'

        mirror_path = "some/random/path/"
        primary = "http://test.ubuntu.com/" + mirror_path
        security = "http://test-security.ubuntu.com/" + mirror_path
        mirrors = {'PRIMARY': primary, 'SECURITY': security}

        # these match default archive prefixes
        opri_pre = "archive.ubuntu.com_ubuntu_dists_xenial"
        osec_pre = "security.ubuntu.com_ubuntu_dists_xenial"
        # this one won't match and should not be renamed defaults.
        other_pre = "dl.google.com_linux_chrome_deb_dists_stable"
        # these are our new expected prefixes
        npri_pre = "test.ubuntu.com_some_random_path_dists_xenial"
        nsec_pre = "test-security.ubuntu.com_some_random_path_dists_xenial"

        files = [
            # orig prefix, new prefix, suffix
            (opri_pre, npri_pre, "_main_binary-amd64_Packages"),
            (opri_pre, npri_pre, "_main_binary-amd64_InRelease"),
            (opri_pre, npri_pre, "-updates_main_binary-amd64_Packages"),
            (opri_pre, npri_pre, "-updates_main_binary-amd64_InRelease"),
            (other_pre, other_pre, "_main_binary-amd64_Packages"),
            (other_pre, other_pre, "_Release"),
            (other_pre, other_pre, "_Release.gpg"),
            (osec_pre, nsec_pre, "_InRelease"),
            (osec_pre, nsec_pre, "_main_binary-amd64_Packages"),
            (osec_pre, nsec_pre, "_universe_binary-amd64_Packages"),
        ]

        expected = sorted([npre + suff for opre, npre, suff in files])
        # create files
        for (opre, npre, suff) in files:
            fpath = os.path.join(apt_lists_d, opre + suff)
            util.write_file(fpath, content=fpath)

        apt_config.rename_apt_lists(mirrors, target)
        found = sorted(os.listdir(apt_lists_d))
        self.assertEqual(expected, found)

    @staticmethod
    def test_apt_proxy():
        """test_apt_proxy - Test apt_*proxy configuration"""
        cfg = {"proxy": "foobar1",
               "http_proxy": "foobar2",
               "ftp_proxy": "foobar3",
               "https_proxy": "foobar4"}

        with mock.patch.object(util, 'write_file') as mockobj:
            apt_config.apply_apt_proxy_config(cfg, "proxyfn", "notused")

        mockobj.assert_called_with('proxyfn',
                                   ('Acquire::http::Proxy "foobar1";\n'
                                    'Acquire::http::Proxy "foobar2";\n'
                                    'Acquire::ftp::Proxy "foobar3";\n'
                                    'Acquire::https::Proxy "foobar4";\n'))

    def test_mirror(self):
        """test_mirror - Test defining a mirror"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "uri": pmir}],
               "security": [{'arches': ["default"],
                             "uri": smir}]}

        mirrors = apt_config.find_apt_mirror_info(cfg)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_default(self):
        """test_mirror_default - Test without defining a mirror"""
        arch = util.get_architecture()
        default_mirrors = apt_config.get_default_mirrors(arch)
        pmir = default_mirrors["PRIMARY"]
        smir = default_mirrors["SECURITY"]
        mirrors = apt_config.find_apt_mirror_info({})

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_arches(self):
        """test_mirror_arches - Test arches selection of mirror"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "uri": "notthis"},
                           {'arches': [util.get_architecture()],
                            "uri": pmir}],
               "security": [{'arches': [util.get_architecture()],
                             "uri": smir},
                            {'arches': ["default"],
                             "uri": "nothat"}]}

        mirrors = apt_config.find_apt_mirror_info(cfg)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_arches_default(self):
        """test_mirror_arches - Test falling back to default arch"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "uri": pmir},
                           {'arches': ["thisarchdoesntexist"],
                            "uri": "notthis"}],
               "security": [{'arches': ["thisarchdoesntexist"],
                             "uri": "nothat"},
                            {'arches': ["default"],
                             "uri": smir}]}

        mirrors = apt_config.find_apt_mirror_info(cfg)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_arches_sysdefault(self):
        """test_mirror_arches - Test arches falling back to sys default"""
        arch = util.get_architecture()
        default_mirrors = apt_config.get_default_mirrors(arch)
        pmir = default_mirrors["PRIMARY"]
        smir = default_mirrors["SECURITY"]
        cfg = {"primary": [{'arches': ["thisarchdoesntexist_64"],
                            "uri": "notthis"},
                           {'arches': ["thisarchdoesntexist"],
                            "uri": "notthiseither"}],
               "security": [{'arches': ["thisarchdoesntexist"],
                             "uri": "nothat"},
                            {'arches': ["thisarchdoesntexist_64"],
                             "uri": "nothateither"}]}

        mirrors = apt_config.find_apt_mirror_info(cfg)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_search(self):
        """test_mirror_search - Test searching mirrors in a list
            mock checks to avoid relying on network connectivity"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "search": ["pfailme", pmir]}],
               "security": [{'arches': ["default"],
                             "search": ["sfailme", smir]}]}

        with mock.patch.object(apt_config, 'search_for_mirror',
                               side_effect=[pmir, smir]) as mocksearch:
            mirrors = apt_config.find_apt_mirror_info(cfg)

        calls = [call(["pfailme", pmir]),
                 call(["sfailme", smir])]
        mocksearch.assert_has_calls(calls)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_search_dns(self):
        """test_mirror_search_dns - Test searching dns patterns"""
        pmir = "phit"
        smir = "shit"
        cfg = {"primary": [{'arches': ["default"],
                            "search_dns": True}],
               "security": [{'arches': ["default"],
                             "search_dns": True}]}

        with mock.patch.object(apt_config, 'get_mirror',
                               return_value="http://mocked/foo") as mockgm:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        calls = [call(cfg, 'primary', util.get_architecture()),
                 call(cfg, 'security', util.get_architecture())]
        mockgm.assert_has_calls(calls)

        with mock.patch.object(apt_config, 'search_for_mirror_dns',
                               return_value="http://mocked/foo") as mocksdns:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        calls = [call(True, 'mirror'),
                 call(True, 'security-mirror')]
        mocksdns.assert_has_calls(calls)

        # first return is for the non-dns call before
        with mock.patch.object(apt_config, 'search_for_mirror',
                               side_effect=[None, pmir, None, smir]) as mockse:
            with mock.patch.object(util, 'subp',
                                   return_value=('host.sub.com', '')) as mocks:
                mirrors = apt_config.find_apt_mirror_info(cfg)

        calls = [call(None),
                 call(['http://ubuntu-mirror.sub.com/ubuntu',
                       'http://ubuntu-mirror.localdomain/ubuntu',
                       'http://ubuntu-mirror/ubuntu']),
                 call(None),
                 call(['http://ubuntu-security-mirror.sub.com/ubuntu',
                       'http://ubuntu-security-mirror.localdomain/ubuntu',
                       'http://ubuntu-security-mirror/ubuntu'])]
        mockse.assert_has_calls(calls)
        mocks.assert_called_with(['hostname', '--fqdn'], capture=True, rcs=[0])

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_search_many3(self):
        """test_mirror_search_many3 - Test all three mirrors specs at once"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "uri": pmir,
                            "search_dns": True,
                            "search": ["pfailme", "foo"]}],
               "security": [{'arches': ["default"],
                             "uri": smir,
                             "search_dns": True,
                             "search": ["sfailme", "bar"]}]}

        # should be called once per type, despite three configs each
        with mock.patch.object(apt_config, 'get_mirror',
                               return_value="http://mocked/foo") as mockgm:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        calls = [call(cfg, 'primary', util.get_architecture()),
                 call(cfg, 'security', util.get_architecture())]
        mockgm.assert_has_calls(calls)

        # should not be called, since primary is specified
        with mock.patch.object(apt_config, 'search_for_mirror_dns') as mockdns:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        mockdns.assert_not_called()

        # should not be called, since primary is specified
        with mock.patch.object(apt_config, 'search_for_mirror') as mockse:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        mockse.assert_not_called()

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_mirror_search_many2(self):
        """test_mirror_search_many2 - Test the two search specs at once"""
        pmir = "http://us.archive.ubuntu.com/ubuntu/"
        smir = "http://security.ubuntu.com/ubuntu/"
        cfg = {"primary": [{'arches': ["default"],
                            "search_dns": True,
                            "search": ["pfailme", pmir]}],
               "security": [{'arches': ["default"],
                             "search_dns": True,
                             "search": ["sfailme", smir]}]}

        # should be called once per type, despite three configs each
        with mock.patch.object(apt_config, 'get_mirror',
                               return_value="http://mocked/foo") as mockgm:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        calls = [call(cfg, 'primary', util.get_architecture()),
                 call(cfg, 'security', util.get_architecture())]
        mockgm.assert_has_calls(calls)

        # this should be the winner by priority, despite config order
        with mock.patch.object(apt_config, 'search_for_mirror',
                               side_effect=[pmir, smir]) as mocksearch:
            mirrors = apt_config.find_apt_mirror_info(cfg)
        calls = [call(["pfailme", pmir]),
                 call(["sfailme", smir])]
        mocksearch.assert_has_calls(calls)

        self.assertEqual(mirrors['MIRROR'],
                         pmir)
        self.assertEqual(mirrors['PRIMARY'],
                         pmir)
        self.assertEqual(mirrors['SECURITY'],
                         smir)

    def test_url_resolvable(self):
        """test_url_resolvable - Test resolving urls"""

        with mock.patch.object(util, 'is_resolvable') as mockresolve:
            util.is_resolvable_url("http://1.2.3.4/ubuntu")
        mockresolve.assert_called_with("1.2.3.4")

        with mock.patch.object(util, 'is_resolvable') as mockresolve:
            util.is_resolvable_url("http://us.archive.ubuntu.com/ubuntu")
        mockresolve.assert_called_with("us.archive.ubuntu.com")

        bad = [(None, None, None, "badname", ["10.3.2.1"])]
        good = [(None, None, None, "goodname", ["10.2.3.4"])]
        with mock.patch.object(socket, 'getaddrinfo',
                               side_effect=[bad, bad, good,
                                            good]) as mocksock:
            ret = util.is_resolvable_url("http://us.archive.ubuntu.com/ubuntu")
            ret2 = util.is_resolvable_url("http://1.2.3.4/ubuntu")
        calls = [call('does-not-exist.example.com.', None, 0, 0, 1, 2),
                 call('example.invalid.', None, 0, 0, 1, 2),
                 call('us.archive.ubuntu.com', None),
                 call('1.2.3.4', None)]
        mocksock.assert_has_calls(calls)
        self.assertTrue(ret)
        self.assertTrue(ret2)

        # side effect need only bad ret after initial call
        with mock.patch.object(socket, 'getaddrinfo',
                               side_effect=[bad]) as mocksock:
            ret3 = util.is_resolvable_url("http://failme.com/ubuntu")
        calls = [call('failme.com', None)]
        mocksock.assert_has_calls(calls)
        self.assertFalse(ret3)

    def test_disable_suites(self):
        """test_disable_suites - disable_suites with many configurations"""
        release = "xenial"
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""

        # disable nothing
        disabled = []
        expect = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable release suite
        disabled = ["$RELEASE"]
        expect = """\
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable other suite
        disabled = ["$RELEASE-updates"]
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # multi disable
        disabled = ["$RELEASE-updates", "$RELEASE-security"]
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # multi line disable (same suite multiple times in input)
        disabled = ["$RELEASE-updates", "$RELEASE-security"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://UBUNTU.com//ubuntu xenial-updates main
deb http://UBUNTU.COM//ubuntu xenial-updates main
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
# suite disabled by curtin: deb http://UBUNTU.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://UBUNTU.COM//ubuntu xenial-updates main
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # comment in input
        disabled = ["$RELEASE-updates", "$RELEASE-security"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
#foo
#deb http://UBUNTU.com//ubuntu xenial-updates main
deb http://UBUNTU.COM//ubuntu xenial-updates main
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
#foo
#deb http://UBUNTU.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://UBUNTU.COM//ubuntu xenial-updates main
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable custom suite
        disabled = ["foobar"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb http://ubuntu.com/ubuntu/ foobar main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
# suite disabled by curtin: deb http://ubuntu.com/ubuntu/ foobar main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable non existing suite
        disabled = ["foobar"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb http://ubuntu.com/ubuntu/ notfoobar main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
deb http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb http://ubuntu.com/ubuntu/ notfoobar main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable suite with option
        disabled = ["$RELEASE-updates"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb [a=b] http://ubu.com//ubu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb [a=b] http://ubu.com//ubu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable suite with more options and auto $RELEASE expansion
        disabled = ["updates"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb [a=b c=d] http://ubu.com//ubu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
# suite disabled by curtin: deb [a=b c=d] \
http://ubu.com//ubu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

        # single disable suite while options at others
        disabled = ["$RELEASE-security"]
        orig = """deb http://ubuntu.com//ubuntu xenial main
deb [arch=foo] http://ubuntu.com//ubuntu xenial-updates main
deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        expect = """deb http://ubuntu.com//ubuntu xenial main
deb [arch=foo] http://ubuntu.com//ubuntu xenial-updates main
# suite disabled by curtin: deb http://ubuntu.com//ubuntu xenial-security main
deb-src http://ubuntu.com//ubuntu universe multiverse
deb http://ubuntu.com/ubuntu/ xenial-proposed main"""
        result = apt_config.disable_suites(disabled, orig, release)
        self.assertEqual(expect, result)

#
# vi: ts=4 expandtab
