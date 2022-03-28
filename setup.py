from setuptools import setup, find_packages
from io import open
from os import path

from base_kivy_app import __version__

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

URL = 'https://github.com/matham/base_kivy_app'

setup(
    name='base_kivy_app',
    version=__version__,
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    license='MIT',
    description=(
        'A base for kivy apps with flat layout and providing '
        'user configuration.'),
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=URL,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    packages=find_packages(),
    install_requires=[
        'ruamel.yaml', 'kivy', 'plyer',
        'pywin32; sys_platform == "win32"',
        'pyobjus; sys_platform == "darwin"', 'tree-config',
        'more-kivy-app'],
    extras_require={
        'dev': ['pytest>=3.6', 'pytest-cov', 'flake8', 'sphinx-rtd-theme',
                'coveralls', 'sphinx'],
    },
    package_data={
        'base_kivy_app':
            ['media/*', '*.kv', 'media/flat_icons/*']},
    project_urls={
        'Bug Reports': URL + '/issues',
        'Source': URL,
    },
)
