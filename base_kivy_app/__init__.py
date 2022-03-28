'''base_kivy_app
=================

A base for kivy apps with flat layout and providing user configuration.
'''
import sys
import os
import pathlib

__all__ = ('get_pyinstaller_datas', )

__version__ = '0.1.2'


def get_pyinstaller_datas():
    """Returns the ``datas`` list required by PyInstaller to be able to package
    :mod:`base_kivy_app` in a application.

    """
    root = pathlib.Path(os.path.dirname(sys.modules[__name__].__file__))
    datas = []
    for pat in ('**/*.kv', '*.kv', 'media/*', 'media/flat_icons/*'):
        for f in root.glob(pat):
            datas.append((str(f), str(f.relative_to(root.parent).parent)))

    return datas
