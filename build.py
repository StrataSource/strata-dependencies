#!/usr/bin/env python3

import subprocess
import shutil
import os
import multiprocessing
import argparse
import glob
import re

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


def get_pkgconf_dir() -> str:
    return f'{get_lib_dir()}/pkgconfig'


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
        'PATH': f'{get_install_dir()}/bin:{os.getenv("PATH")}',
        'PKG_CONFIG_PATH': f'{get_lib_dir()}/pkgconfig',
        'HOME': f'{os.getenv("HOME")}'
    }


def download_and_extract(url: str, type: str, path: str) -> bool:
    r = subprocess.run(['curl', '-L', '-o', f'download-1.{type}', url])
    if r.returncode != 0:
        os.unlink(f'download-1.{type}')
        return False
    with WorkDir(f'{get_top()}/repos'):
        if type == 'tar.gz' or type == 'tar' or type == 'tar.bz2' or type == 'tgz':
            os.mkdir(path)
            r = subprocess.run(['tar', '--verbose', '--strip-components=1', '-xf', f'../download-1.{type}', '-C', path])
        elif type == 'zip':
            r = subprocess.run(['unzip', f'../download-1.{type}', '-d', path])
        else:
            assert False
    os.unlink(f'download-1.{type}')
    return r.returncode == 0


def add_pc_lib(pc: str, libs: list[str]) -> bool:
    """
    Hack to add libs to a .pc pkg config file

    Parameters
    ----------
    pc: str
        Path to the pkg config file
    libs: list[str]
        Libs to add, including the -l part. These are just flags

    Returns
    -------
        True if ok
    """
    subst = ' '.join(libs)
    l = []
    with open(pc, 'r') as fp:
        l = fp.readlines()

    for i in range(0,len(l)):
        if l[i].startswith('Libs:') and not l[i].endswith(subst):
            l[i] = f'{l[i].strip()} {subst}\n'

    # Write it out
    with open(pc, 'w') as fp:
        fp.writelines(l)
    return True


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

    def download(self) -> bool:
        """
        Called if the directory returned by get_directory() does not exist
        
        Returns
        -------
            True if download + extract succeeded
        """
        return False

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
        return []


    def get_headers(self) -> list[str]:
        """
        Returns a list of directories that contain headers that should be installed
        These will be copied into release/include
        """
        return []


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
        dir = f'{get_top()}/repos/{self.get_directory()}'
        if not os.path.exists(dir):
            if not self.download():
                print('Download failed!')
                return False

        with WorkDir(dir):
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
            if subprocess.run(a, shell=kwargs['shell'] if 'shell' in kwargs else False, env=e, capture_output=quiet).returncode != 0:
                return False
        return True


class Dep_autoconf(Dependency):

    def get_directory(self) -> str:
        return 'autoconf'
    
    def configure(self) -> bool:
        return self._execute_cmds(
            ['./bootstrap'],
            ['./configure', f'--prefix={get_install_dir()}']
        )

    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_libffi(Dependency):

    def get_directory(self) -> str:
        return 'libffi'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-static', '--enable-shared=no', '--enable-tools=no', '--enable-tests=no',
             '--enable-samples=no', '--disable-docs', f'--prefix={get_install_dir()}'],
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

class Dep_pcre2(Dependency):

    def get_directory(self) -> str:
        return 'pcre2'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-static', '--enable-shared=no', f'--prefix={get_install_dir()}',
             '--enable-utf', '--enable-pcre2-16', '--enable-pcre2-32'],
            env={'CFLAGS': '-fPIC'}
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_bzip2(Dependency):

    def get_directory(self) -> str:
        return 'bzip2'

    def get_artifacts(self) -> list[str]:
        return ['libbz2.so.1.0']

    def configure(self) -> bool:
        return True

    def build(self) -> bool:
        return self._execute_cmds(
            ['make', 'install', f'-j{nproc()}', 'CFLAGS=-fPIC', f'PREFIX={get_install_dir()}'],
            # Build shared too. Needed for the precompiled libav that we already have. (No install rule for this makefile either)
            ['make', '-f', 'Makefile-libbz2_so', f'-j{nproc()}', 'CFLAGS=-fPIC', f'PREFIX={get_install_dir()}'],
            ['cp', 'libbz2.so.1.0', f'{get_lib_dir()}/libbz2.so.1.0'],
            env={'CFLAGS': '-fPIC'}
        )



class Dep_curl(Dependency):

    def get_directory(self) -> str:
        return 'curl'

    def get_artifacts(self) -> list[str]:
        return ['libcurl.a']

    def configure(self) -> bool:
        return self._execute_cmds(
            ['cmake', '-Bbuild', '-GNinja', '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={get_install_dir()}',
             '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_C_FLAGS=-fPIC', '-DCMAKE_CXX_FLAGS=-fPIC']
        )

    def build(self) -> bool:
        return self._execute_cmds(
            ['ninja', '-C', 'build', 'install']
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
            ['meson', 'setup', 'build', '-Dgtk=disabled', '-Dlibpng=disabled', '-Dtests=disabled',
             '--prefix', get_install_dir(), '--buildtype', 'release',
             '--libdir', 'lib', '--pkg-config-path', f'{get_lib_dir()}/pkgconfig',
             '--build.pkg-config-path', f'{get_lib_dir()}/pkgconfig', '-Ddefault_library=static',
             f'--prefix={get_install_dir()}'],
            env={'CFLAGS': '-fPIC'}
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install', f'-j{nproc()}'])


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
            ['./autogen.sh', '--enable-static=no', f'--prefix={get_install_dir()}', f'--with-expat={get_install_dir()}', '--sysconfdir=/etc', '--disable-docs', 
                f'--datadir={get_install_dir()}/share', '--disable-cache-build', '--with-baseconfigdir=/etc/fonts'],
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
        return True
    
    def build(self) -> bool:
        return all([
            # build only!
            self._execute_cmds(['make', f'-j{nproc()}', 'install-exec']),
        ])


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
            ['meson', 'setup', 'build', '-Ddefault_library=static', f'--prefix={get_install_dir()}',
             '-Dtests=false', '-Ddocs=false', '--buildtype', 'release', '--libdir=lib'],
            env={'CFLAGS': '-fPIC'}
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])


class Dep_cairo(Dependency):

    def get_directory(self) -> str:
        return 'cairo'
    
    def get_artifacts(self) -> list[str]:
        return ['libcairo.so']

    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'setup', 'build', '-Dxlib=enabled', '-Dxlib-xcb=enabled', '-Dtests=disabled',
             '-Dquartz=disabled', '-Dgtk_doc=false', '-Dfreetype=enabled', '-Dfontconfig=enabled',
             f'--prefix={get_install_dir()}', '--buildtype', 'release',
             '--libdir=lib'],
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
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])


class Dep_harfbuzz(Dependency):

    def get_directory(self) -> str:
        return 'harfbuzz'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'setup', 'build', f'--prefix={get_install_dir()}', '-Ddefault_library=static', '-Dtests=disabled', '--buildtype', 'release',
             '--libdir=lib'],
            env={
                'CFLAGS': f'-fPIC',
                'LDFLAGS': f'-L{get_lib_dir()} -L{get_lib_dir()}',
                'FREETYPE_CFLAGS': f'-I{get_inc_dir()}/freetype2'
            }
        )

    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])


class Dep_libdatrie(Dependency):

    def get_directory(self) -> str:
        return 'libdatrie'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-shared=no', '--enable-static', f'--prefix={get_install_dir()}'],
            env={
                # The build setup for datrie is a bit messed up it seems. First time you build it you get an error with VERSION being undefined
                # but the second pass works. As a workaround we'll just define VERSION here
                'CFLAGS': '-fPIC -DVERSION=\\"HACK\\"'
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_libthai(Dependency):

    def get_directory(self) -> str:
        return 'libthai'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-shared=no', '--enable-static', f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC'
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_pango(Dependency):
    
    def get_directory(self) -> str:
        return 'pango'
    
    def get_artifacts(self) -> list[str]:
        return [
            'libpango-1.0.so',
            'libpangocairo-1.0.so',
            'libpangoft2-1.0.so'
        ]
    
    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'setup', 'build', '--prefix', get_install_dir(), '--buildtype', 'release',
             '--libdir', 'lib', '--pkg-config-path', f'{get_lib_dir()}/pkgconfig',
             '--build.pkg-config-path', f'{get_lib_dir()}/pkgconfig', '--buildtype', 'release',
            ],
            env={
                'CFLAGS': f'-fPIC -I{get_inc_dir()}/freetype2 -w -Wno-error', # Disable errors...
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined -L{get_lib_dir()}',
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])


class Dep_librsvg(Dependency):
    
    def get_directory(self) -> str:
        return 'librsvg'
    
    def get_artifacts(self) -> list[str]:
        return [
            'librsvg_2.a'
        ]
    
    def configure(self) -> bool:
        return self._execute_cmds(
            ['meson', 'setup', 'build', '--prefix', get_install_dir(), '--buildtype', 'release',
             '--libdir', 'lib', '--pkg-config-path', f'{get_lib_dir()}/pkgconfig',
             '--build.pkg-config-path', f'{get_lib_dir()}/pkgconfig',
            ],
            env={
                'CFLAGS': f'-fPIC', # Disable errors...
                'LDFLAGS': f'-L{get_lib_dir()} -Wl,--no-undefined -L{get_lib_dir()}',
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])


class Dep_Xiph(Dependency):
    """
    Common base class for all Xiph-maintained dependencies, since they all share the
    same build facility
    """

    def __init__(self, dep: str):
        self.dep = dep

    def get_directory(self) -> str:
        return self.dep

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./autogen.sh'],
            ['./configure', '--enable-shared=no', '--enable-static', f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC'
            }
        )

    def build(self) -> bool:
        if not self._execute_cmds(['make', 'install', f'-j{nproc()}']):
            return False
        
        match self.dep:
            case 'ogg':
                return add_pc_lib(f'{get_pkgconf_dir()}/ogg.pc', ['-lm'])
            case 'vorbis':
                return all([
                    add_pc_lib(f'{get_pkgconf_dir()}/vorbis.pc', ['-logg', '-lm']),
                    add_pc_lib(f'{get_pkgconf_dir()}/vorbisenc.pc', ['-lvorbis', '-logg', '-lm']),
                    add_pc_lib(f'{get_pkgconf_dir()}/vorbisfile.pc', ['-lvorbis', '-logg', '-lm']),
                ])
            case 'opus':
                return add_pc_lib(f'{get_pkgconf_dir()}/opus.pc', ['-lm'])
        return True


class Dep_mpg123(Dependency):

    def get_directory(self) -> str:
        return 'mpg123'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['autoreconf', '-iv'],
            ['./configure', '--with-optimization=2', '--enable-shared=no', '--enable-static', f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC'
            }
        )

    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_mp3lame(Dependency):

    def download(self) -> bool:
        return download_and_extract('https://sourceforge.net/projects/lame/files/lame/3.100/lame-3.100.tar.gz/download', 'tar.gz', 'mp3lame')

    def get_directory(self) -> str:
        return 'mp3lame'

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./configure', '--enable-shared=no', '--enable-static', f'--prefix={get_install_dir()}'],
            env={
                'CFLAGS': '-fPIC'
            }
        )

    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])



class Dep_libsndfile(Dependency):

    def get_directory(self) -> str:
        return 'libsndfile'

    def get_artifacts(self) -> list[str]:
        return ['libsndfile.so']

    def configure(self) -> bool:
        return self._execute_cmds(
            #['autoreconf', '-iv'],
            ['rm', '-rf', 'build'],
            ['cmake', '-Bbuild', '-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF', 
             '-DBUILD_SHARED_LIBS=ON', '-DBUILD_PROGRAMS=OFF', '-DBUILD_EXAMPLES=OFF', f'-DCMAKE_INSTALL_PREFIX={get_install_dir()}',
             '-DENABLE_PACKAGE_CONFIG=OFF'],
            #['./configure', '--enable-shared', '--disable-static', '--disable-full-suite', f'--prefix={get_install_dir()}'],
            # TODO: Can't get it to build with cmake yet, but the library is looking to remove autotools. fix this!
            #['cmake', '.', '-B', 'build', '-DBUILD_SHARED_LIBS=ON', '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF',
            # '-DCMAKE_SHARED_LINKER_FLAGS=-lmvec', '-DCMAKE_C_FLAGS=-ffast-math', f'-DCMAKE_INSTALL_PREFIX={get_install_dir()}'],
            env={
                'CFLAGS': f'-fPIC -ffast-math -I{get_inc_dir()}',
                'LDFLAGS': f'-L{get_lib_dir()}',
                'LIBS': '-lmp3lame -lm',
                #'FLAC_CFLAGS': '',
                #'FLAC_LIBS': '-Wl,-Bstatic -lflac',
                #'OGG_CFLAGS': '',
                #'OGG_LIBS': '-Wl,-Bstatic -logg',
                #'VORBIS_CFLAGS': '',
                #'VORBIS_LIBS': '-Wl,-Bstatic -lvorbis',
                #'VORBISENC_CFLAGS': '',
                #'VORBISENC_LIBS': '-Wl,-Bstatic -lvorbisenc',
                'OPUS_CFLAGS': f'-I{get_inc_dir()}/include/opus',
                'OPUS_LIBS': '-Wl,-Bstatic -lopus -Wl,-Bdynamic',
                'MPG123_CFLAGS': '',
                'MPG123_LIBS': '-Wl,-Bstatic -lmpg123 -Wl,-Bdynamic'
            }
        )

    def build(self) -> bool:
        # TODO: cmake
        #return self._execute_cmds(['make', '-C', 'build', 'install', f'-j{nproc()}'])
        return self._execute_cmds(['ninja', '-C', 'build', 'install'])



class Dep_ffmpeg(Dependency):

    def get_directory(self) -> str:
        return 'ffmpeg'
    
    def get_artifacts(self) -> list[str]:
        return [
            'libavcodec.a',
            'libavformat.a',
            #'libavdevice.a', # Probably don't need this
            'libavfilter.a',
            'libavutil.a',
            'libswscale.a',
            'libswresample.a'
        ]
    
    def get_headers(self) -> list[str]:
        return [
            'libavcodec',
            'libavformat',
            'libavdevice',
            'libavfilter',
            'libavutil',
            'libswresample',
            'libswscale'
        ]
    
    def configure(self) -> bool:
        return self._execute_cmds(
            ['./configure', '--disable-avx', '--disable-avx2', '--disable-sse42', '--disable-sse4',
             f'--prefix={get_install_dir()}', '--enable-libvorbis', '--enable-libopus', '--disable-programs',
             '--disable-doc']
        )

    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


class Dep_icu(Dependency):

    def __init__(self, version: str):
        self.version = version

    def get_directory(self) -> str:
        return 'icu'
    
    def get_artifacts(self):
        artifacts = []
        bins = ['libicudata', 'libicui18n', 'libicuio', 'libicutu', 'libicuuc']
        artifacts += [f'{b}.so.{self.version}' for b in bins]
        artifacts += [f'{b}.so.{self.version.split(".")[0]}' for b in bins]
        return artifacts

    def configure(self) -> bool:
        return self._execute_cmds(
            ['./icu4c/source/configure', f'--prefix={get_install_dir()}'],
            env={
                # The build setup for datrie is a bit messed up it seems. First time you build it you get an error with VERSION being undefined
                # but the second pass works. As a workaround we'll just define VERSION here
                #'CFLAGS': '-fPIC -DVERSION=\\"HACK\\"'
            }
        )
    
    def build(self) -> bool:
        return self._execute_cmds(['make', 'install', f'-j{nproc()}'])


def get_soname(lib: str) -> str|None:
    """
    Returns the SONAME attribute of the ELF file, if it exists. Otherwise returns None
    """
    result = subprocess.run(['readelf', '-d', f'{get_lib_dir()}/{lib}'], capture_output=True)
    if result.returncode != 0:
        return None
    data = result.stdout.decode('utf-8')
    try:
        matches = re.search(r'soname: \[(.*)]$', data, re.MULTILINE)
        return matches.group(1)
    except:
        return None

    
def mkdir_p(path: str) -> bool:
    comps = path.split('/')
    if len(comps) <= 0:
        return False
    p = comps[0]
    for i in range(1, len(comps)):
        if not os.path.exists(p):
            os.mkdir(p)
        p += '/' + comps[i]
    if not os.path.exists(p):
        os.mkdir(p)
    return True


def install_lib(lib: str):
    soname = get_soname(lib)
    if soname is None:
        soname = lib
    if not lib.endswith('.a'):
        shutil.copy(f'{get_lib_dir()}/{soname}', f'release/bin/linux64/{soname}')
    shutil.copy(f'{get_lib_dir()}/{lib}', f'release/lib/external/linux64/{lib}')


def install_headers(dir: str, dst: str):
    shutil.copytree(f'{get_inc_dir()}/{dir}', f'{dst}/{dir}', dirs_exist_ok=True)


def create_release(deps: Dict[str, Dependency]):
    mkdir_p('release/bin/linux64')
    mkdir_p('release/lib/external/linux64')
    mkdir_p('release/include')

    for d in deps:
        # Install binary artifacts
        artifacts = deps[d].get_artifacts()
        for a in artifacts:
            install_lib(a)
        # Install headers
        headers = deps[d].get_headers()
        for h in headers:
            install_headers(h, 'release/include')

    # Strip everything
    for c in glob.glob('release/**/*.so*', recursive=True):
        subprocess.run(['strip', '-x', c])
        subprocess.run(['chrpath', '-d', c])
        if verbose:
            print(f'strip -x {c}')
            print(f'chrpath -d {c}')

    # Create a tarball
    name = shutil.make_archive('release-linux-x86_64', 'gztar', 'release')
    print(f'Created {name}')


def main():
    deps: Dict[str,Dependency]  = {
        'autoconf': Dep_autoconf(),
        'curl': Dep_curl(),
        'pcre': Dep_pcre(),
        'pcre2': Dep_pcre2(),
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
        'fribidi': Dep_fribidi(),
        'libdatrie': Dep_libdatrie(),
        'libthai': Dep_libthai(),
        'cairo': Dep_cairo(),
        'harfbuzz': Dep_harfbuzz(),
        'pango': Dep_pango(),
        'ogg': Dep_Xiph('ogg'),
        'flac': Dep_Xiph('flac'),
        'vorbis': Dep_Xiph('vorbis'),
        'opus': Dep_Xiph('opus'),
        'mpg123': Dep_mpg123(),
        'mp3lame': Dep_mp3lame(),
        'libsndfile': Dep_libsndfile(),
        'ffmpeg': Dep_ffmpeg(),
        'icu': Dep_icu('67.1'),
        #'librsvg': Dep_librsvg(),
    }

    parser = argparse.ArgumentParser()
    parser.add_argument('--only', dest='ONLY', nargs='+', choices=deps.keys(), help='Only build the specified deps')
    parser.add_argument('--quiet', action='store_true', help='Quiet build output')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--clean', action='store_true', help='Cleans the build environment')
    parser.add_argument('--only-release', action='store_true', dest='only_release', help='Only assemble a release from install/')
    parser.add_argument('--skip-release', action='store_true', dest='skip_release', help='Skip assembling of tar.gz')
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
    
    if args.only_release:
        create_release(deps)
        exit(0)
    
    # Create install dirs
    if not os.path.exists('install'):
        os.mkdir('install')
    
    # Build all requested deps
    print(args.ONLY)
    for dep in deps:
        if args.ONLY is not None and dep not in args.ONLY:
            continue
        print(f'Building {dep}')
        if not deps[dep].execute():
            print(f'Build failed for {dep}')
            exit(1)
    print('Finished building all dependencies')

    if not args.skip_release:
        create_release(deps)

if __name__ == '__main__':
    main()
