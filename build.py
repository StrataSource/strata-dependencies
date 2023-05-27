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


def get_inc_dir() -> str:
    return f'{get_install_dir()}/include'


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
        """
        Configures the build
        
        Returns
        -------
            True if configure succeeded
        """
        raise NotImplementedError
    
    
    def build(self) -> bool:
        """
        Runs the build
        This is where you'll run ninja, make, etc.
        
        Returns
        -------
            True if build passed
        """
        raise NotImplementedError
    
    
    def get_artifacts(self) -> list[str]:
        """
        Returns a list of artifacts, relative to the install/lib folder.
        For release artifacts, the SONAME property of the specified library is read and used. So, you may
        specify libcairo.so, but libcairo.so.2 will end up in bin/linux64.
        For the engine repo zip (which is for lib/external/linux64), the files returned from this method are used directly
        """
        raise []


    def get_directory(self) -> str:
        """
        Returns the directory this dependency resides in
        """
        raise NotImplementedError


    def execute(self) -> bool:
        """
        Runs all build steps associated with this dependency
        Applies patches, configures and builds
        """
        with WorkDir(f'{get_top()}/{self.get_directory()}'):
            if not self.apply_patches():
                print('Failed to apply patches')
                return False
            if not self.configure():
                print('Configure failed!')
                return False
            if not self.build():
                print('Build failed!')
                return False
        return True


    def apply_patches(self) -> bool:
        """
        Apply any patches to your dependency here
        
        Returns
        -------
            True if patches were applied successfully
        """
        return True


    @staticmethod
    def _apply_patch(patch: str) -> bool:
        """
        Apply a single patch from file, only if it needs to be applied
        
        Parameters
        ----------
        patch : str
            Path to the patch, relative to the top directory.
        
        Returns
        -------
            True if the patch is already applied or was successfully applied
        """
        if Dependency._execute_cmds(['git', 'apply', '--reverse', '--check', f'{get_top()}/{patch}']):
            return True
        return Dependency._execute_cmds(
            ['git', 'apply', f'{get_top()}/{patch}']
        )


    @staticmethod
    def _apply_patches(patches: list[str]) -> bool:
        """
        Applies a list of patches. See _apply_patch
        """
        for p in patches:
            if not Dependency._apply_patch(p):
                return False
        return True


    @staticmethod
    def _execute_cmds(*args, **kwargs) -> bool:
        """
        Executes a command list, bailing out if any fails
        
        Parameters
        ----------
        *args :
            List of lists to invoke as commands. These are passed directly to subprocess.run
        **kwargs :
            Additional key'ed arguments.
            For now only 'env' is supported. This is a dict that is merged with get_global_env() and
            passed to subprocess.run
        
        Returns
        -------
            True if execution succeeded
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


class Dep_jsonc(Dependency):

    def get_directory(self) -> str:
        return 'json-c'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['cmake', '.', '-B', 'build', '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_STATIC_LIBS=ON', '-DBUILD_SHARED_LIBS=OFF', f'-DCMAKE_INSTALL_PREFIX={get_install_dir()}', '-DDISABLE_EXTRA_LIBS=ON'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', '-C', 'build', 'install', f'-j{nproc()}'])


class Dep_expat(Dependency):

    def get_directory(self) -> str:
        return 'libexpat/expat'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./buildconf.sh'],
            ['./configure', '--without-docbook', '--without-examples', '--without-tests', '--enable-static', '--enable-shared=no', f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_fontconfig(Dependency):

    def get_directory(self) -> str:
        return 'fontconfig'


    def get_artifacts(self) -> list[str]:
        return ['libfontconfig.so']


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh', '--enable-static=no', f'--prefix={get_install_dir()}', f'--with-expat={get_install_dir()}'],
            env={
                'CFLAGS': f'-fPIC -I{get_inc_dir()}',
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined',
                'FREETYPE_CFLAGS': f'-I{get_inc_dir()}/freetype2 -I{get_inc_dir()}/freetype2/freetype',
                'FREETYPE_LIBS': f'-L{get_lib_dir()} -lfreetype',
                'EXPAT_CFLAGS': '',
                'EXPAT_LIBS': f'{get_lib_dir()}/libexpat.a',
                'JSONC_CFLAGS': f'-I{get_inc_dir()}/json-c',
                'JSONC_LIBS': f'{get_lib_dir()}/libjson-c.a'
            }
        )
    
    
    def apply_patches(self) -> bool:
        return self._apply_patch('patches/fontconfig/002-add-face-sub.patch')
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


# Needed for fribidi
class Dep_c2man(Dependency):

    def get_directory(self) -> str:
        return 'c2man'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./Configure', '-s', '-d', '-e'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        if not self._execute_cmds(['make', f'-j{nproc()}']):
            return False
        # No install rules for some reason, gotta manually copy
        shutil.copy('c2man', f'{get_install_dir()}/bin/c2man')
        return True


class Dep_fribidi(Dependency):

    def get_directory(self) -> str:
        return 'fribidi'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh', f'--prefix={get_install_dir()}', '--enable-shared=no', '--enable-static'],
            env={'CFLAGS': '-fPIC'}
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_cairo(Dependency):

    def get_directory(self) -> str:
        return 'cairo'
    
    
    def get_artifacts(self) -> list[str]:
        return ['libcairo.so']


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh', '--enable-xlib=no', '--enable-xlib-xrender=no', '--enable-xlib-xcb=no', 
             '--enable-xcb-shm=no', '--enable-ft', '--enable-egl=no', '--without-x', '--enable-glx=no',
             '--enable-wgl=no', '--enable-quartz=no', '--enable-svg=yes', '--enable-pdf=yes',
             '--enable-ps=yes', '--enable-gobject=no', '--enable-png', '--disable-static', f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC',
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined',
                'pixman_LIBS': f'{get_lib_dir()}/libpixman-1.a',
                'png_LIBS': f'{get_lib_dir()}/libpng.a',
                'FREETYPE_LIBS': f'-L{get_lib_dir()} -lfreetype',
                'FREETYPE_CFLAGS': f'-I{get_inc_dir()}/freetype2',
                'FONTCONFIG_LIBS': f'-L{get_lib_dir()} -lfontconfig'
            }
        )
    
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_harfbuzz(Dependency):

    def get_directory(self) -> str:
        return 'harfbuzz'


    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh', f'--prefix={get_install_dir()}', '--enable-shared=no', '--enable-static'],
            env={
                'CFLAGS': f'-fPIC',
                'LDFLAGS': f'-L{get_lib_dir()} -L{get_lib_dir()}',
                'FREETYPE_CFLAGS': f'-I{get_inc_dir()}/freetype2'
            }
        )

    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_pango(Dependency):
    
    def get_directory(self) -> str:
        return 'pango'
    
    
    def apply_patches(self) -> bool:
        return self._apply_patches([
            'patches/pango/001-add-face-sub.patch',
            #'patches/pango/meson-cairo.patch'
        ])
    
    
    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'build', '--prefix', get_install_dir(), '--buildtype', 'release',
             '--libdir', 'lib', '--pkg-config-path', f'{get_lib_dir}/pkgconfig',
             #'--build.pkg-config.path', f'{get_lib_dir()}/pkgconfig'
            ],
            env={
                'CFLAGS': '-fPIC',
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined'
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])



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
        'json-c': Dep_jsonc(),
        'libexpat': Dep_expat(),
        'fontconfig': Dep_fontconfig(),
        'c2man': Dep_c2man(),
        'fribidi': Dep_fribidi(),
        'cairo': Dep_cairo(),
        'harfbuzz': Dep_harfbuzz(),
        'pango': Dep_pango()
    }
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', dest='ONLY', nargs='*', choices=deps.keys(), help='Only build the specified deps')
    parser.add_argument('--quiet', action='store_true', help='Quiet build output')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--clean', action='store_true', help='Cleans the build environment')
    args = parser.parse_args()
    
    os.chdir(get_top())
    
    # Clean if requested
    if args.clean:
        os.remove(get_install_dir())
        subprocess.run(['git', 'submodule', 'foreach', 'git', 'clean', '-ffdx'])
        exit(0)
    
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