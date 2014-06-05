#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from distutils.core import setup, Command

name_ = 'chemreac'
version_ = '0.2.0-dev'

DEBUG = True if os.environ.get('USE_DEBUG', False) else False
USE_OPENMP = True if os.environ.get('USE_OPENMP', False) else False

# Make `python setup.py test` work without depending on py.test being installed
# https://pytest.org/latest/goodpractises.html
class PyTest(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        import sys,subprocess
        # py.test --genscript=runtests.py
        errno = subprocess.call([sys.executable, 'runtests.py'])
        raise SystemExit(errno)

cmdclass_ = {'test': PyTest}

if '--help'in sys.argv[1:] or sys.argv[1] in (
        '--help-commands', 'egg_info', 'clean', '--version'):
    # Enbale pip to probe setup.py before all requirements are installed
    ext_modules_ = []
else:
    import pickle
    from pycompilation.dist import clever_build_ext, CleverExtension
    cmdclass_['build_ext'] = clever_build_ext
    subsd = {'USE_OPENMP': USE_OPENMP}
    ext_modules_ = [
        CleverExtension(
            "chemreac._chemreac",
            sources=[
                'src/chemreac_template.cpp',
                'src/finitediff/finitediff/fornberg.f90',
                'src/finitediff/finitediff/c_fornberg.f90',
                'chemreac/_chemreac.pyx',
            ],
            template_regexps=[
                (r'^(\w+)_template.(\w+)$', r'\1.\2', subsd),
            ],
            pycompilation_compile_kwargs={
                'per_file_kwargs': {
                    'src/chemreac.cpp': {
                        'std': 'c++0x',
                        # 'fast' doesn't work on drone.io
                        'options': ['pic', 'warn'] +\
                        (['openmp'] if USE_OPENMP else []),
                        'defmacros': ['restrict=__restrict__', 'DEBUG']+\
                        (['DEBUG'] if DEBUG else []),
                    },
                },
                'options': ['pic', 'warn'],
                'defmacros': ['restrict=__restrict__'],
            },
            pycompilation_link_kwargs={
                'options': (['openmp'] if USE_OPENMP else []),
                'std': 'c++0x',
            },
            include_dirs=['src/', 'src/finitediff/finitediff/'],
            logger=True,
        )
    ]

setup(
    name=name_,
    version=version_,
    description='Python extension for reaction diffusion.',
    author='Björn Dahlgren',
    author_email='bjodah@DELETEMEgmail.com',
    url='https://bitbucket.org/bjodah/'+name_,
    packages=[name_],
    cmdclass = cmdclass_,
    ext_modules = ext_modules_,
)
