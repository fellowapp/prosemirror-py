from setuptools import find_packages, setup

try:
    import pypandoc

    long_description = pypandoc.convert_file("README.md", "rst", "md")
except (IOError, ImportError):
    long_description = open("README.md").read()

setup(
    name="prosemirror_py",
    version="0.1.0",
    packages=find_packages(exclude=["contrib", "docs", "tests", "example.py"]),
    include_package_data=True,
    license="MIT License",
    description="Prosemirror in Python",
    long_description=long_description,
    url="https://github.com/fellowinsights/prosemirror_py",
    author="Shen Li",
    author_email="shen@fellow.co",
    install_requires=[],
    classifiers=[
        "Intended Audience :: Developers",
        "LICENSE :: OTHER/PROPRIETARY LICENSE",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    extras_require={},
)
