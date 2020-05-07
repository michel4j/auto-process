from setuptools import setup, find_packages
from autoprocess.version import get_version

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='autoprocess',
    version=get_version(),
    url="https://github.com/michel4j/autoprocess",
    license='MIT',
    author='Michel Fodje',
    author_email='michel4j@gmail.com',
    description='AutoProcess',
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords='Automated Data Processing for MX',
    include_package_data=True,
    packages=find_packages(),
    package_data={
        'autoprocess': [
            'share/*.*',
            'parsers/data/*.*',
            'utils/data/*.*',
        ]
    },
    install_requires=requirements,
    scripts=[
        'bin/auto.analyse',
        'bin/auto.inputs',
        'bin/auto.integrate',
        'bin/auto.process',
        'bin/auto.report',
        'bin/auto.powder',
        'bin/auto.scale',
        'bin/auto.strategy',
        'bin/auto.symmetry',
        'bin/auto.server',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
