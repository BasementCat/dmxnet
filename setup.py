from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='dmxnet',
    version='0.1',
    packages=['dmxnet'],
    install_requires=['crc8'],
    extras_require={
        'DmxPy': ['dmxpy'],
    },
    entry_points={
        'console_scripts': [
            'dmxnet = dmxnet.bin.node:main',
        ],
    },

    # metadata to display on PyPI
    author='BasementCat',
    description='Send DMX data over the network.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT License',
    keywords='DMX USB Lighting',
    url='https://github.com/basementcat/dmxnet',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Environment :: Console',
    ],
)
