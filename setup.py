import setuptools
from spotify_terminal import common

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='spotify-terminal-marcdjulien',  
    version='{}.{}.{}'.format(*common.get_version()),
    scripts=['spotify-terminal.py'] ,
    author="Marc-Daniel Julien",
    author_email="marcdjulien@gmail.com",
    description="Terminal Spotify application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/marcdjulien/spotify-terminal",
    packages=setuptools.find_packages(),
    package_data={"spotify_terminal": ['.*']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    install_requires=['requests']
)