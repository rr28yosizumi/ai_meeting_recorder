from setuptools import setup, find_packages

setup(
    name='ai_meeting_recorder',
    version='0.1.0',
    description='会議録音・議事録作成ツール',
    author='R-28',
    author_email='rr28_yosizumi@hotmail.com',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    install_requires=[
        'numpy',
        'scipy',
        'sounddevice',
        'matplotlib',
        'pyyaml',
        'pydub',
        'tkinter',
        'audioop-lts',
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'ai_meeting_recorder=src.main:main',
        ],
    },
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
