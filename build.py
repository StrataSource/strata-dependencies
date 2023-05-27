#!/usr/bin/env python3

import requests
import subprocess
import shutil
import os
import multiprocessing
import argparse
import glob

from contextlib import AbstractContextManager

from typing import Dict


quiet = False
verbose = False

def nproc() -> int:
    return multiprocessing.cpu_count()


def get_top() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def get_install_dir() -> str:
    return f'{get_top()}/install'


def get_lib_dir() -> str:
    return f'{get_install_dir()}/lib'


def get_global_subs() -> dict:
    return {
        'INSTALLDIR': f'{get_install_dir()}',
        'INCDIR': f'{get_install_dir()}/include',
        'LIBDIR': f'{get_lib_dir()}',
        'VERSION_SCRIPT': f'-Wl,--version-script={get_top()}/version_script.txt'
    }


def get_global_env() -> dict:
    return {
        'CC': 'gcc',
        'CXX': 'g++',
        'PKG_CONFIG': 'pkg-config --static',
        'PATH': f'{os.getenv("PATH")}:{get_install_dir()}/bin',
        'PKG_CONFIG_PATH': f'{get_lib_dir()}/pkgconfig'
    }


class WorkDir(AbstractContextManager):
    
    def __init__(self, dir: str) -> None:
        self.dir = dir
    
    
    def __enter__(self):
        self.saved = os.getcwd()
        os.chdir(self.dir)
        return self
    
    
    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        os.chdir(self.saved)



class Dependency:
    """
    Base for all dependencies
    """

    def configure(self) -> bool:
        raise NotImplementedError
    
    
    def build(self) -> bool:
        raise NotImplementedError
    
    
    def get_artifacts(self) -> list[str]:
        raise []


    def get_directory(self) -> str:
        raise NotImplementedError


    def execute(self) -> bool:
        with WorkDir(f'{get_top()}/{self.get_directory()}'):
            if not self.configure():
                print('Configure failed!')
                return False
            if not self.build():
                print('Build failed!')
                return False
        return True


    @staticmethod
    def _execute_cmds(*args, **kwargs) -> bool:
        """
        Executes a command list, bailing out if any fails
        Returns true on success
        """
        for a in args:
            e = get_global_env()
            if 'env' in kwargs:
                e.update(kwargs['env'])
            if verbose:
                print(f'args={a}, env={e}')
            if subprocess.run(a, shell=False, env=e, capture_output=quiet).returncode != 0:
                return False
        return True



class Dep_libffi(Dependency):

    def get_directory(self) -> str:
        return 'libffi'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-static', '--enable-shared=no', '--enable-tools=no', '--enable-tests=no',
             '--enable-samples=no', f'--prefix={get_install_dir()}'],
             env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_zlib(Dependency):

    def get_directory(self) -> str:
        return 'zlib'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./configure', '--static', '--64', f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_pcre(Dependency):

    def get_directory(self) -> str:
        return 'pcre'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-static', '--enable-shared=no', f'--prefix={get_install_dir()}',
             '--enable-utf', '--enable-pcre16', '--enable-pcre32'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_bzip2(Dependency):

    def get_directory(self) -> str:
        return 'bzip2'


    def configure(self) -> bool:
        return True

    
    def build(self) -> bool:
        return self._execute_cmds(
            ['make', 'install', f'-j{nproc()}', 'CFLAGS=-fPIC', f'PREFIX={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )



class Dep_glib(Dependency):

    def get_directory(self) -> str:
        return 'glib'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'build', '--buildtype', 'release', '--default-library', 'static', '--prefix', 
             get_install_dir(), '--libdir', get_lib_dir()],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        if not self._execute_cmds(['ninja', '-C', 'build', 'install']):
            return False
        shutil.copy(f'{get_install_dir()}/lib/glib-2.0/include/glibconfig.h',
                    f'{get_install_dir()}/include/glib-2.0/glibconfig.h')
        return True


class Dep_pixman(Dependency):

    def get_directory(self) -> str:
        return 'pixman'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh', '--enable-gtk=no', '--enable-png=no', '--enable-shared=no', '--enable-static',
             f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_brotli(Dependency):

    def get_directory(self) -> str:
        return 'brotli'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./bootstrap'],
            ['./configure', '--enable-static', '--disable-shared', f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_libpng(Dependency):

    def get_directory(self) -> str:
        return 'libpng'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./configure', '--enable-static', '--disable-shared', f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        if not self._execute_cmds(['make', 'install', f'-j{nproc()}']):
            return False
        # --disable-shared does nothing!
        for s in glob.glob(f'{get_install_dir()}/lib/libpng*.so'):
            os.remove(s)
        return True



class Dep_freetype(Dependency):

    def get_directory(self) -> str:
        return 'freetype'


    def get_artifacts(self) -> list[str]:
        return ['libfreetype.so']


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--with-harfbuzz=no', '--disable-static', '--enable-shared',
            f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC',
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined',
                'ZLIB_LIBS': '' ,
                'BZIP2_LIBS': '',
                'LIBPNG_LIBS': f'{get_lib_dir()}/libpng.a -lbz2 -lz -lm',
                'BROTLI_LIBS': f'{get_lib_dir()}/libbrotlidec.a {get_lib_dir()}/libbrotlienc.a {get_lib_dir()}/libbrotlicommon.a'
            }
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])




def main():
    deps: Dict[str,Dependency]  = {
        'pcre': Dep_pcre(),
        'zlib': Dep_zlib(),
        'libffi': Dep_libffi(),
        'bzip2': Dep_bzip2(),
        'glib': Dep_glib(),
        'pixman': Dep_pixman(),
        'brotli': Dep_brotli(),
        'libpng': Dep_libpng(),
        'freetype': Dep_freetype(),
    }
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', dest='ONLY', nargs='*', choices=deps.keys(), help='Only build the specified deps')
    parser.add_argument('--quiet', action='store_true', help='Quiet build output')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    args = parser.parse_args()
    
    os.chdir(get_top())
    
    global quiet
    quiet = args.quiet
    global verbose
    verbose = args.verbose
    
    # Create install dirs
    if not os.path.exists('install'):
        os.mkdir('install')
    
    # Build all requested deps
    for dep in deps:
        if args.ONLY is not None and dep not in args.ONLY:
            continue
        print(f'Building {dep}')
        if not deps[dep].execute():
            print('Build failed')
            exit(1)
    print('Finished building all dependencies')

main()