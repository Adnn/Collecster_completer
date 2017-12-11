#!/usr/bin/env python
from main import Date, Store, Collecster, TemplateConfig, listFiles

from selenium import webdriver

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test program, filling in Collecster web interface")
    parser.add_argument("picturefolder", help="A folder containing the pictures to be added to Occurrences.")
    parser.add_argument("--credentials-file", default="credentials.json", 
                        help="A JSON file with 'username' and 'password' keys")
    args = parser.parse_args()

    # Create a new instance of the Firefox driver
    driver = webdriver.Chrome()

    try:
        collecster = Collecster(TemplateConfig())
        collecster.login(driver, args.credentials_file)

        store = Store()
        store.concept.name = "Test Concept"
        store.concept.urls = ["http/1", "http/2"]
        store.concept.developer = "Sega"

        store.release.barcode = 111222333444
        store.release.publisher = "Namco"
        store.release.date = Date("1998")

        print(store)

        #collecster.prefillConcept(driver, store.concept)
        #collecster.prefillRelease(driver, store)
        file_list = listFiles(args.picturefolder, "jpg")
        collecster.prefillOccurrence(driver, store, iter(file_list))

        input("Press any key to exit...")

    finally:
        driver.quit()

