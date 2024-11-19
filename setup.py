from setuptools import setup, find_packages

setup(
    name="sqlython",
    version="1.2.1",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "mysql-connector-python",
    ],
    author="Fauzi NS",
    author_email="fauzi.ns@icloud.com",
    description="A lightweight and user-friendly SQL query builder for Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/uziins/sqlython",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
