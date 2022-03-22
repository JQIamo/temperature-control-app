import os
import setuptools
from setuptools.command.build_ext import build_ext as build_ext_orig


class build_ext(build_ext_orig):
    def run(self):
        directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temperature_web_control/web/")

        command = ['npm', '--prefix', directory, 'install']
        self.announce(f"install web dependencies: {command}")

        self.spawn(command)

        command = ['npm', '--prefix', directory, 'run', 'build']
        self.announce(f"building web assets: {command}")

        self.spawn(command)

        super().run()


setuptools.setup(
    name='temperature-control-app',
    version='1.0',
    url='https://github.com/JQIamo/temperature-control-app',
    license='MIT License',
    author='Yanda Geng',
    author_email='gengyd@umd.edu',
    description='Access and monitor your favorite temperature controllers from your browser.',
    long_description='A web dashboard for monitoring and controlling temperature controllers.',
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires='>=3.7',
    install_requires=['pyyaml', 'requests', 'pyserial', 'websockets'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'temperature-app=temperature_web_control.main:main'
        ]
    },
    cmdclass={
        'build_ext': build_ext,
    },
    include_package_data=True,
)