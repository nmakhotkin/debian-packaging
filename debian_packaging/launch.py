#!/usr/bin/python
# Copyright (c) 2015 SUSE Linux GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import argparse
import os
import platform
import sys

from jinja2 import contextfilter
from jinja2 import contextfunction
from jinja2 import Environment
from jinja2 import FileSystemLoader

import yaml

from debian_packaging import versions
from debian_packaging import utils


def _context_epoch(context, pkg_name):
    """get the epoch (or 0 if unknown) for the given pkg name"""
    return context['epochs'].get(pkg_name, 0)


def _context_py2name(context, pkg_name):
    return utils.get_debian_name(pkg_name, context['impl'])


def _context_py3name(context, pkg_name):
    return utils.get_debian_name(pkg_name, 'cpython3')


def _context_py3pkg(context, pkg_name, pkg_version=None):
    return _context_py2pkg(context, pkg_name, pkg_version=None, impl='cpython3')


def _context_py2pkg(context, pkg_name, pkg_version=None, impl=None):
    """generate a distro specific package name with optional version tuple."""
    # package name handling
    if impl:
        name = utils.get_debian_name(pkg_name, impl)
    else:
        name = utils.get_debian_name(pkg_name, context['impl'])

    # if no pkg_version is given, look in the requirements and set one
    if not pkg_version:
        if pkg_name in context['requirements']:
            pkg_version = ('>=', context['requirements'][pkg_name])

    # pkg_version is a tuple with comparator and number, i.e. "('>=', '1.2.3')"
    if pkg_version:
        # epoch handling
        if pkg_name in context['epochs'].keys():
            epoch = '%s:' % context['epochs'][pkg_name]
        else:
            epoch = ''
        v_comparator, v_number = pkg_version
        v_str = ' (%s %s%s)' % (v_comparator, epoch, v_number)
    else:
        v_str = ''

    return '%s%s' % (name, v_str)


def _context_license_spdx(context, value):
    """convert a given known spdx license to another one"""
    # more values can be taken from from https://github.com/hughsie/\
    #    appstream-glib/blob/master/libappstream-builder/asb-package-rpm.c#L76
    mapping = {
        "Apache-1.1": "ASL 1.1",
        "Apache-2.0": "ASL 2.0",
        "BSD-3-Clause": "BSD",
        "GPL-1.0+": "GPL+",
        "GPL-2.0": "GPLv2",
        "GPL-2.0+": "GPLv2+",
        "GPL-3.0": "GPLv3",
        "GPL-3.0+": "GPLv3+",
        "LGPL-2.1": "LGPLv2.1",
        "LGPL-2.1+": "LGPLv2+",
        "LGPL-2.0": "LGPLv2 with exceptions",
        "LGPL-2.0+": "LGPLv2+ with exceptions",
        "LGPL-3.0": "LGPLv3",
        "LGPL-3.0+": "LGPLv3+",
        "MIT": "MIT with advertising",
        "MPL-1.0": "MPLv1.0",
        "MPL-1.1": "MPLv1.1",
        "MPL-2.0": "MPLv2.0",
        "Python-2.0": "Python",
    }

    if context['spec_style'] == 'debian':
        return mapping[value]
    else:
        # just use the spdx license name
        return value


###############
# jinja2 filter
###############
@contextfilter
def _filter_license_spdx(context, value):
    return _context_license_spdx(context, value)


@contextfilter
def _filter_epoch(context, value):
    return _context_epoch(context, value)


################
# jinja2 globals
################
@contextfunction
def _globals_py2pkg(context, pkg_name, pkg_version=None):
    return _context_py2pkg(context, pkg_name, pkg_version)


@contextfunction
def _globals_epoch(context, value):
    return _context_epoch(context, value)


@contextfunction
def _globals_license_spdx(context, value):
    return _context_license_spdx(context, value)


@contextfunction
def _globals_py2name(context, value):
    return _context_py2name(context, value)


@contextfunction
def _globals_py3name(context, value):
    return _context_py3name(context, value)


@contextfunction
def _globals_py3pkg(context, pkg_name, pkg_version=None):
    return _context_py3pkg(context, pkg_name, pkg_version)


def _env_register_filters_and_globals(env):
    """register all the jinja2 filters we want in the environment"""
    env.filters['license'] = _filter_license_spdx
    env.filters['epoch'] = _filter_epoch
    env.globals['py2pkg'] = _globals_py2pkg
    env.globals['py3pkg'] = _globals_py3pkg
    env.globals['py2name'] = _globals_py2name
    env.globals['py3name'] = _globals_py3name
    env.globals['epoch'] = _globals_epoch
    env.globals['license'] = _globals_license_spdx


def generate_spec(spec_style, epochs, requirements, input_template_path, impl):
    """generate a spec file with the given style and the given template"""
    env = Environment(loader=FileSystemLoader(
        os.path.dirname(input_template_path)))

    _env_register_filters_and_globals(env)

    template = env.get_template(os.path.basename(input_template_path))
    return template.render(
        spec_style=spec_style,
        epochs=epochs,
        requirements=requirements,
        impl=impl
    )


def _get_default_distro():
    distname, version, id_ = platform.linux_distribution()
    print("distro = %s" % distname)
    if "debian" in distname.lower():
        return "debian"
    elif "ubuntu" in distname.lower():
        return "ubuntu"
    else:
        return "unknown"


def _get_default_template():
    fns = [f for f in os.listdir('.')
           if os.path.isfile(f) and f.endswith('.spec.j2')]
    if not fns:
        return None, ("No *.control.j2 templates found. "
                      "See `renderspec-deb -h` for usage.")
    elif len(fns) > 1:
        return None, ("Multiple *.control.j2 templates found, "
                      "please specify one.\n"
                      "See `renderspec-deb -h` for usage.")
    else:
        return fns[0], None


def _get_epochs(filename):
    """get a dictionary with pkg-name->epoch mapping"""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = yaml.load(f.read())
            return dict(data['epochs'])
    return {}


def _get_requirements(filenames):
    """get a dictionary with pkg-name->min-version mapping"""
    reqs = {}
    for filename in filenames:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                reqs.update(versions.get_requirements(f.readlines()))
    return reqs


def process_args():
    distro = _get_default_distro()
    parser = argparse.ArgumentParser(
        description="Convert a .control.j2 template into a .control"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output filename or '-' for stdout. "
             "default: autodetect"
    )
    parser.add_argument(
        "--spec-style",
        help="distro style you want to use. "
             "default: %s" % (distro),
        default=distro,
        choices=['ubuntu', 'debian']
    )
    parser.add_argument(
        "--epochs",
        help="yaml file with epochs listed. "
             "default: %s-epochs.yaml" % distro,
        default="%s-epochs.yaml" % distro
    )
    parser.add_argument(
        "input-template",
        nargs='?',
        help="specfile jinja2 template to render. "
             "default: *.control.j2"
    )
    parser.add_argument(
        "--requirements",
        help="file(s) which contain "
             "PEP0508 compatible requirement lines. Last mentioned "
             "file has highest priority. default: %(default)s",
        action='append',
        default=[]
    )
    parser.add_argument(
        "--impl",
        help="Python implementation which is used to search packages."
             "default: %s" % 'cpython2',
        default='cpython2',
        choices=['cpython2', 'cpython3']
    )

    return vars(parser.parse_args())


def main():
    args = process_args()

    # autodetect input/output fns if possible
    input_template = args['input-template']
    if not input_template:
        input_template, errmsg = _get_default_template()
        if not input_template:
            print(errmsg)
            return 1
    output_fn = args['output']
    if not output_fn:
        if not input_template.endswith('.control.j2'):
            print("Failed to autodetect output file name. "
                  "Please specify using `-o/--output`.")
            return 2
        output_fn, _, _ = input_template.rpartition('.')

    epochs = _get_epochs(args['epochs'])
    requirements = _get_requirements(args['requirements'])
    spec = generate_spec(
        args['spec_style'],
        epochs,
        requirements,
        input_template,
        args['impl']
    )
    if output_fn and output_fn != '-':
        print("Rendering: %s -> %s" % (input_template, output_fn))
        with open(output_fn, "w") as o:
            o.write(spec)
    else:
        print(spec)
    return 0


if __name__ == '__main__':
    sys.exit(main())