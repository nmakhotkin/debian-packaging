import pickle
import re
from os import path

from debian_packaging.utils import version


DIRNAME = path.dirname(__file__)[:-6]
PYDIST_RE = re.compile(r"""
    (?P<name>[A-Za-z][A-Za-z0-9_.\-]*)             # Python distribution name
    \s*
    (?P<vrange>(?:-?\d\.\d+(?:-(?:\d\.\d+)?)?)?) # version range
    \s*
    (?P<dependency>(?:[a-z][^;]*)?)              # Debian dependency
    (?:  # optional upstream version -> Debian version translator
        ;\s*
        (?P<standard>PEP386)?                    # PEP-386 mode
        \s*
        (?P<rules>(?:s|tr|y).*)?                 # translator rules
    )?
    """, re.VERBOSE)


def memoize(func):
    if not hasattr(func, 'cache'):
        setattr(func, 'cache', {})

    def decorator(*args, **kwargs):
        key = pickle.dumps((args, kwargs))
        if key not in func.cache:
            func.cache[key] = func(*args, **kwargs)
        return func.cache[key]
    return decorator


@memoize
def load_pydist_file(impl='cpython2'):
    """Load iformation about installed Python distributions.

    :param impl: interpreter implementation, f.e. cpython2, cpython3, pypy
    :type impl: str
    """
    fpath = '%s/pydist/%s_fallback' % (DIRNAME, impl)

    result = {}
    with open(fpath) as fp:
        for line in fp:
            line = line.strip('\r\n')
            if line.startswith('#') or not line:
                continue
            dist = PYDIST_RE.search(line)
            if not dist:
                raise Exception('invalid pydist line: %s (in %s)' % (line, fpath))
            dist = dist.groupdict()
            name = dist['name']
            dist['versions'] = version.get_requested_versions(impl, dist['vrange'])
            dist['dependency'] = dist['dependency'].strip()
            if dist['rules']:
                dist['rules'] = dist['rules'].split(';')
            else:
                dist['rules'] = []
            result.setdefault(name, []).append(dist)
    return result


def normalize_name(name):
    return name.replace('-', '_')


def make_name_python(name, impl='cpython2'):
    pkg = re.sub("-python$", "", name)
    pkg = re.sub("_", "-", pkg).lower()
    if not pkg.startswith("python-") or not pkg.startswith("python3-"):
        pkg = "%s%s" % (_get_pkg_prefix(impl), pkg)
    return pkg


def _get_pkg_prefix(impl):
    return 'python-' if impl == 'cpython2' else 'python3-'


def get_debian_name(python_pkg, impl='cpython2'):
    python_pkg = normalize_name(python_pkg)

    pydist = load_pydist_file(impl)

    if python_pkg in pydist:
        return pydist[python_pkg][0]['dependency']

    print("WARNING: Required package not found in the list: %s" % python_pkg)
    print("WARNING: Trying transform to form '%s*..." % _get_pkg_prefix(impl))

    debian_pkg = make_name_python(python_pkg, impl)
    print("WARNING: The program doesn't guarantee that the following package exists: %s" % debian_pkg)
    print("====================================================")

    return debian_pkg
