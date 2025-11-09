"""Setup configuration for M5.3 Data Quality & Validation package"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="m5-3-data-quality-validation",
    version="1.0.0",
    author="Module 5.3 Team",
    description="Production-ready data quality validation for RAG systems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yesvisare/ccc_l2_aug_practical",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=8.0.1",
            "pytest-asyncio>=0.23.5",
        ],
    },
)
