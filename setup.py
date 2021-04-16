from setuptools import setup, find_packages
from re import search

with open("faraday_cli/__init__.py", "rt", encoding="utf8") as f:
    version = search(r"__version__ = \"(.*?)\"", f.read()).group(1)


install_requires = [
    "click>=7.1.2",
    "colorama>=0.4.4",
    "faraday-plugins>=1.4.5",
    "jsonschema>=3.2.0",
    "PyYAML>=5.4.1",
    "simple-rest-client>=1.0.8",
    "tabulate>=0.8.9",
    "validators>=0.18.2",
    "spinners>=0.0.24",
    "termcolor>=1.1.0",
    "cmd2>=1.5.0",
    "log-symbols>=0.0.14",
]


extra_req = {
    "dev": ["giteasychangelog", "flake8", "black", "pre-commit"],
    "test": ["pytest", "pytest-cov", "faradaysec"],
    "docs": [
        "mkdocs",
        "mkdocs-material",
    ],
}

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("RELEASE.md") as history_file:
    history = history_file.read()


setup(
    name="faraday-cli",
    version=version,
    packages=find_packages(include=["faraday_cli", "faraday_cli.*"]),
    url="https://github.com/infobyte/faraday-cli",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    license="GNU General Public License v3",
    author="Faradaysec",
    python_requires=">3.7.0",
    author_email="devel@faradaysec.com",
    long_description=readme + "\n\n" + history,
    long_description_content_type="text/markdown",
    description="Faraday cli package",
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extra_req,
    entry_points={
        "console_scripts": ["faraday-cli=faraday_cli.shell.main:main"],
    },
)
