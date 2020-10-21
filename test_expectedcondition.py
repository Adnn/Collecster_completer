#!/usr/bin/env python
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from selenium.webdriver.common.by import By

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test program, waiting for partial text in a given element")
    args = parser.parse_args()

    # Create a new instance of the Firefox driver
    driver = webdriver.Chrome()

    try:
        driver.get("https://www.google.fr")

        WebDriverWait(driver, 3).until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#_eEe"), "offered in"))

        input("Press any key to exit...")

    finally:
        driver.quit()

