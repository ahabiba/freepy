from setuptools import setup, find_packages

setup(
    name="freepy",
    version="1.0.1",
    packages=find_packages('src'),
    package_dir = {'':'src'},
    install_requires=['pykka == 1.2.1', 'llist == 0.4', 'twisted == 15.5.0'],
    include_package_data = True,
    author="Thomas Quintana",
    author_email="quintana.thomas@gmail.com",
    license="Apache License 2.0",
    url="https://github.com/thomasquintana/freepy",
    entry_points={
        'console_scripts': [
          'freepy-server = freepy.run:main',
        ]
    }
)

