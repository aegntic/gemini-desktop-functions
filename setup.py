#!/usr/bin/env python3
"""
Setup script for Gemini Linux Function Manager
"""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read the version from src/__init__.py
about = {}
with open(os.path.join("src", "__init__.py"), "r", encoding="utf-8") as f:
    exec(f.read(), about)

# Read the requirements
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if not line.startswith("#")]

# Read the README
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="gemini-linux-function-manager",
    version=about["__version__"],
    description="Native Linux desktop application for Google Gemini with custom function management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",  # Update with your name
    author_email="your.email@example.com",  # Update with your email
    url="https://github.com/yourusername/gemini-desktop-mcp-functions",  # Update with your GitHub URL
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gemini-function-manager=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",  # Update with your chosen license
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
)
