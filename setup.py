from setuptools import setup, find_packages
from re import search

with open('faraday_cli/__init__.py', 'rt', encoding='utf8') as f:
    version = search(r'__version__ = \'(.*?)\'', f.read()).group(1)


install_requires = [
    'Click',
    'validators',
    'colorama',
    'simple-rest-client',
    'faraday-plugins',
    'PyYAML',
    'tabulate',
    'jsonschema'

]


setup(
    name='faraday-cli',
    version=version,
    packages=find_packages(include=['faraday_cli', 'faraday_cli.*']),
    url='',
    license='',
    author='Faradaysec',
    author_email='devel@faradaysec.com',
    description='Faraday cli package',
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
            'console_scripts': [
                'faraday-cli=faraday_cli.cli.faraday:cli',
            ],
        },
)
