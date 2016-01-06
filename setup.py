from setuptools import setup, find_packages

setup(
    name = "freepy",
    version = "2.0.0",
    packages = find_packages('src'),
    package_dir = { '':'src' },
    install_requires=[ 'jinja2 == 2.8', 'llist == 0.4',
                       'pykka == 1.2.1', 'twisted == 15.5.0' ],
    include_package_data = True,
    author = "Thomas Quintana",
    author_email = "quintana.thomas@gmail.com",
    license = "Apache License 2.0",
    url = "https://github.com/thomasquintana/freepy",
    entry_points = {
        'console_scripts': [
          'freepy-server = freepy.run:main',
        ]
    }
)

