from setuptools import setup, find_packages
from re import search

with open('faraday_cli/__init__.py', 'rt', encoding='utf8') as f:
    version = search(r'__version__ = \'(.*?)\'', f.read()).group(1)


install_requires = [
    'Click',
    'colorama',
    'faraday-plugins',
    'jsonschema',
    'PyYAML',
    'simple-rest-client',
    'tabulate',
    'validators',
]


extra_req = {
        'dev': [
            'giteasychangelog',
            'flake8',
            'pre-commit'
        ],
        'test': [
            'pytest',
            'pytest-cov',
            'faradaysec',
        ],
    }


setup(
    name='faraday-cli',
    version=version,
    packages=find_packages(include=['faraday_cli', 'faraday_cli.*']),
    url='https://github.com/infobyte/faraday-cli',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    license="GNU General Public License v3",
    author='Faradaysec',
    author_email='devel@faradaysec.com',
    description='Faraday cli package',
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extra_req,
    entry_points={
            'console_scripts': [
                'faraday-cli=faraday_cli.cli.faraday:cli',
            ],
        },
)
