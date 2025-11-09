"""
Setup configuration for M5.1 Incremental Indexing package.
"""

from setuptools import setup, find_packages

setup(
    name="m5_1_incremental_indexing",
    version="1.0.0",
    description="Efficient incremental indexing for vector databases",
    author="CCC L2",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "pinecone-client>=3.0.3",
        "openai>=1.12.0",
        "python-dotenv>=1.0.1",
        "fastapi>=0.109.2",
        "uvicorn[standard]>=0.27.1",
        "pydantic>=2.6.1",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.4",
            "jupyter>=1.0.0",
            "ipykernel>=6.29.0",
            "notebook>=7.0.7",
        ],
        "monitoring": [
            "prometheus-client>=0.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "m5-detect=m5_1_incremental_indexing.core:main",
        ],
    },
)
