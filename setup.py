import pathlib

import setuptools

long_description = pathlib.Path("README.md").read_text()
required_packages = pathlib.Path("requirements.txt").read_text().splitlines()

setuptools.setup(
    name="zntrack",
    version="0.4.2",
    author="zincwarecode",
    author_email="zincwarecode@gmail.com",
    description="A Python package for parameter and data version control with DVC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zincware/ZnTrack",
    download_url="https://github.com/zincware/ZnTrack/archive/beta.tar.gz",
    keywords=["dvc", "machine learning", "parameter tracking"],
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=required_packages,
)
