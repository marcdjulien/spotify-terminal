import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="spotify-terminal",  
    version="0.15.1",
    scripts=["spotify-terminal.py"] ,
    author="Marc-Daniel Julien",
    author_email="marcdjulien@gmail.com",
    description="Terminal Spotify application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/marcdjulien/spotify-terminal",
    packages=setuptools.find_packages(),
    package_data={"spotify_terminal": [".*", "pdc34dll/*"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    install_requires=["requests"]
)
