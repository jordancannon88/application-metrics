import setuptools

with open("README.md") as fp:
    long_description = fp.read()

setuptools.setup(
    name="applicationmetrics",
    version="0.0.1",

    description="A sample CDK Python app that stores and retrieves user metrics for applications",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="Jordan Cannon",

    package_dir={"": "applicationmetrics"},
    packages=setuptools.find_packages(where="applicationmetrics"),

    install_requires=[
        "aws-cdk.core",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: Apache Software License",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
