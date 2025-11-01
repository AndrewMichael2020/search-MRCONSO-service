from setuptools import setup, Extension
import pybind11

ext_modules = [
    Extension(
        'cppmatch',
        ['cppmatch.cpp'],
        include_dirs=[pybind11.get_include()],
        language='c++',
        extra_compile_args=['-std=c++11'],
    ),
]

setup(
    name='cppmatch',
    version='0.1.0',
    author='Andrew Michael',
    description='BK-tree fuzzy string matching with pybind11',
    ext_modules=ext_modules,
    install_requires=['pybind11'],
    zip_safe=False,
)
