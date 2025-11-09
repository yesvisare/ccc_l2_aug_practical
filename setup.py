"""
Setup configuration for Module 8.2: A/B Testing for RAG Improvements

Install with: pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = [
        line.strip()
        for line in requirements_path.read_text().splitlines()
        if line.strip() and not line.startswith('#')
    ]

setup(
    name="m8-ab-testing-rag",
    version="1.0.0",
    description="A/B Testing framework for RAG Improvements",
    author="TVH Framework",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "m8-ab-testing=m8_ab_testing_rag.ab_testing:main",
        ],
    },
)
