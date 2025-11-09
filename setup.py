"""
Setup configuration for M6.3 RBAC package
"""

from setuptools import setup, find_packages

setup(
    name="m6_rbac",
    version="1.0.0",
    description="Module 6.3: RBAC & Multi-Level Access Control for RAG systems",
    author="CCC L2 Course",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "sqlalchemy>=2.0.23",
        "psycopg2-binary>=2.9.9",
        "alembic>=1.12.1",
        "casbin>=1.36.2",
        "casbin-sqlalchemy-adapter>=1.5.0",
        "redis>=5.0.1",
        "pinecone-client>=2.2.4",
        "python-dotenv>=1.0.0",
        "passlib>=1.7.4",
        "bcrypt>=4.1.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "httpx>=0.25.2",
            "jupyter>=1.0.0",
            "ipykernel>=6.27.1",
            "notebook>=7.0.6",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
        ],
    },
)
