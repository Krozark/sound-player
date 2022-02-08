import os

import setuptools

from sound_player import __version__


def read(fname):
   return open(os.path.join(os.path.dirname(__file__), fname)).read()

setuptools.setup(
   name='sound-player',
   version=__version__,
   description='The aim of this project is to create multi playlist player',
   long_description=read('README.md'),
   long_description_content_type="text/markdown",
   license="BSD2",
   author='Maxime Barbier',
   author_email='maxime.barbier1991+ava@gmail.com',
   url="https://github.com/Krozark/sound-player",
   keywords="sound player",
   packages=setuptools.find_packages(),
   install_requires=[
      'krozark-current-platform',
   ],
   classifiers=[
      "Programming Language :: Python",
      "Programming Language :: Python :: 3",
      "Operating System :: OS Independent",
    ],
   python_requires='>=3.6',
)