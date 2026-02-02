from setuptools import setup, find_packages

setup(
    name="kino-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot==20.7",
        "python-dotenv==1.0.0",
    ],
)
