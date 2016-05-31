# Copyright © 2012-2013 Piotr Ożarowski <piotr@debian.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import logging
import re

SHEBANG_RE = re.compile(r'''
    (?:\#!\s*){0,1}  # shebang prefix
    (?P<path>
        .*?/bin/.*?)?
    (?P<name>
        python|pypy)
    (?P<version>
        \d[\.\d]*)?
    (?P<debug>
        -dbg)?
    (?P<options>.*)
    ''', re.VERBOSE)
EXTFILE_RE = re.compile(r'''
    (?P<name>.*?)
    (?:\.
        (?P<stableabi>abi\d+)
     |(?:\.
        (?P<soabi>
            (?P<impl>cpython|pypy)
            -
            (?P<ver>\d{2})
            (?P<flags>[a-z]*)
        )?
        (?:
            (?:(?<!\.)-)?  # minus sign only if soabi is defined
            (?P<multiarch>[^/]*?)
        )?
    ))?
    (?P<debug>_d)?
    \.so$''', re.VERBOSE)
log = logging.getLogger('dhpython')


class Interpreter:
    """
    :attr path: /usr/bin/ in most cases
    :attr name: pypy or python (even for python3 and python-dbg) or empty string
    :attr version: interpreter's version
    :attr debug: -dbg version of the interpreter
    :attr impl: implementation (cpytho2, cpython3 or pypy)
    :attr options: options parsed from shebang
    :type path: str
    :type name: str
    :type version: Version or None
    :type debug: bool
    :type impl: str
    :type options: tuple
    """
    path = '/usr/bin/'
    name = 'python'
    version = None
    debug = False
    impl = ''
    options = ()
    _cache = {}

    def __init__(self, value=None, path=None, name=None, version=None,
                 debug=None, impl=None, options=None):
        params = locals()
        del params['self']
        del params['value']

        for key, val in params.items():
            if val is not None:
                setattr(self, key, val)
            elif key == 'version':
                setattr(self, key, val)

    def __repr__(self):
        result = self.path
        if not result.endswith('/'):
            result += '/'
        result += self._vstr(self.version)
        if self.options:
            result += ' ' + ' '.join(self.options)
        return result

    def __str__(self):
        return self._vstr(self.version)

    def _vstr(self, version=None, consider_default_ver=False):
        if self.impl == 'pypy':
            # TODO: will Debian support more than one PyPy version?
            return self.name
        version = version or self.version or ''
        if consider_default_ver and (not version or version == self.default_version):
            version = '3' if self.impl == 'cpython3' else ''
        elif isinstance(version, Version) and version == Version(major=2):
            version = ''  # do not promote /usr/bin/python2
        if self.debug:
            return 'python{}-dbg'.format(version)
        return self.name + str(version)

    def binary(self, version=None):
        return '{}{}'.format(self.path, self._vstr(version))

    @property
    def binary_dv(self):
        """Like binary(), but returns path to default intepreter symlink
        if version matches default one for given implementation.
        """
        return '{}{}'.format(self.path, self._vstr(consider_default_ver=True))

    @property
    def default_version(self):
        if self.impl:
            return default(self.impl)


# due to circular imports issue
from debian_packaging.utils.version import Version, default
