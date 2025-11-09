"""Setup configuration for M6.4 Compliance & Audit Logging"""

from setuptools import setup, find_packages

setup(
    name="m6_4_compliance_audit",
    version="1.0.0",
    description="Module 6.4: Compliance & Audit Logging for RAG Applications",
    author="TVH Framework",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn==0.24.0",
        "pydantic==2.5.0",
        "elasticsearch==8.11.0",
        "python-dotenv==1.0.0",
        "python-logstash-async==2.5.0",
        "cryptography==41.0.7",
        "prometheus-client==0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.3",
            "pytest-asyncio==0.21.1",
        ],
    },
)
