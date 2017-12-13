#!/usr/bin/env python
from main import Store, TemplateConfig, GiantBomb

from selenium import webdriver

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test program, looking up a game for a given platform on GiantBomb.")

    # Create a new instance of the Firefox driver
    driver = webdriver.Chrome()

    try:
        store = Store()
        store.concept.name = "spy vs spy"

        config = TemplateConfig()

        giantbomb = GiantBomb(config)
        giantbomb.openName(driver, store)
        giantbomb.scrapValues(driver, store)

        assert(store.concept.urls[0] == "https://www.giantbomb.com/spy-vs-spy/3030-15637/")

        print("Success !")

    finally:
        input("Press any key to exit...")
        driver.quit()


