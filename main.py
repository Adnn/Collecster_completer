#!/usr/bin/env python
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait, Select # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import urllib.parse

from termcolor import colored

import argparse
import glob
import json
import os.path


def loadPage(driver, url, parametersDict=None):
    if parametersDict:
        url = url + "?{}".format(urllib.parse.urlencode(parametersDict))
    driver.get(url)
    driver.set_page_load_timeout(30)
    return Webpage(driver)



def scrapValue(driver, selector, expectedLabel):
    labelElement = driver.find_element_by_css_selector(selector)
    if (labelElement.text != expectedLabel):
        message = "ERROR: missed the '{}' entry".format(expectedLabel)
        print(colored(message, "red"))
        raise Exception(message)

    return labelElement.find_element_by_xpath("../..") \
                       .find_element_by_css_selector("td").text

#def waitForElement(driver, selector):
def waitForTitle(driver, title):
    # give a good 100h to login
    WebDriverWait(driver, 360000).until(EC.title_is(title))
    

def openWindow(driver, url="_blank"):
    ## All other attempts did not work
    #driver.find_element_by_tag_name("body").send_keys(Keys.chord(Keys.COMMAND, "n"))

    #act = ActionChains(driver)
    #act.key_down(Keys.COMMAND).send_keys("t").key_up(Keys.COMMAND).perform()

    driver.execute_script("window.open('', '{}', 'toolbar=1,location=0,menubar=1');".format(url))


class TemplateConfig:
    def __init__(self):
        self.concept = {}
        self.concept["nature"] = "Game";

        self.release = {}
        self.release["release_region"] = "EU"
        self.release["system_specification"] = "Master System cartridge game [NTSC-U, PAL]"
        self.release["attributes"] = [
                "[content]self",
                "[papers]manual",
                "[packaging]cartridge box",
                "[packaging]hang on tab",
                "[packaging]seal brand",
        ] 

        self.occurrence = {}
        self.occurrence["origin"] = "Original"
        self.occurrence["working_condition"] = "Yes"
        self.occurrence["pictures"] = [
                {"pictures-{index}-detail": "Front", "pictures-{index}-any_attribute": "[packaging]cartridge box"},
                {"pictures-{index}-detail": "Back",  "pictures-{index}-any_attribute": "[packaging]cartridge box"},
                {"pictures-{index}-detail": "Group"},
                {"pictures-{index}-detail": "Side label", "pictures-{index}-any_attribute": "[packaging]cartridge box"},
        ] 


class Concept:
    def __init__(self):
        self.urls = []
    pass

class Release:
    pass

class Store:
    def __init__(self):
        self.concept = Concept()
        self.release = Release()

    def __str__(self):
        lines = []  
        for key, value in self.__dict__.items():
            lines.append("{}: {}".format(key, value.__dict__))
        return "\n".join(lines)

class Date:
    def __init__(self, value):
        blocks = value.split("-")
        if len(blocks) == 3:
            self.partial_date = value
            self.precision = "Day"
        elif len(blocks) == 2:
            self.partial_date = "{}-01".format(value)
            self.precision = "Month"
        elif len(blocks) == 1:
            self.partial_date = "{}-01-01".format(value)
            self.precision = "Year"

    def __repr__(self):
        return "{}({})".format(self.partial_date, self.precision)

    def fill(self, webpage):
        webpage.setText("partial_date", self.partial_date)
        webpage.setRadio("partial_date_precision", self.precision)


class Webpage:
    def __init__(self, driver):
        self.driver = driver
        
    def fieldNameToId(self, name):
       return "id_{}".format(name.lower().replace(" ", "_")) 

    def findField(self, field_name):
        return self.driver.find_element_by_id(self.fieldNameToId(field_name))

    def fillText(self, element, value):
        element.send_keys(value)

    def fillSelect(self, element, value):
        Select(element).select_by_visible_text(value)

    def setText(self, field_name, value):
        self.fillText(self.findField(field_name), value)

    def setSelect(self, field_name, value):
        try:
            self.fillSelect(self.findField(field_name), value)
        except NoSuchElementException:
            print(colored("Unable to fill {}, please complete it manually".format(field_name), "yellow"))
            return False
        return True

    def requireSelect(self, field_name, value):
        if not self.setSelect(field_name, value):
            input("Please manually fill {} then press a to resume processing...".format(field_name))

    def setRadio(self, field_name, value):
        self.findField(field_name).find_element_by_xpath("./label[normalize-space(text()) = '{}']/input".format(value)).click()

    def dictToFields(self, dictionary):
        for key, value in dictionary.items():
            self.setText(key, value)

    def extendInlines(self, table_body_selector, requested_size):
        table_body = self.driver.find_element_by_css_selector(table_body_selector)
        count = len(table_body.find_elements_by_css_selector("tr.form-row"))
        # The last form_row is empty_form, so is not used
        while (count-1) < requested_size:
            self.driver.execute_script("document.querySelector(\"{} .add-row > td > a\").click()"
                                            .format(table_body_selector))
            count += 1
        return table_body

    def setInlines(self, inlineInfo, values):
        table_body = self.extendInlines(inlineInfo["table"], len(values))
        for i in range(len(values)):
            element = table_body.find_element_by_css_selector(inlineInfo["field"].format(index=i))
            value = values[i]
            if element.tag_name == "input":
                self.fillText(element, value)
            elif element.tag_name == "select":
                self.fillSelect(element, value)

    def submit(self, form_id):
        self.driver.find_element_by_id(form_id).submit()


class SegaRetro:
    # The nested table is not always inside the same tr index
    # Hopefully, it will always be the only nested table
    date_selector = "#mw-content-text > div:nth-child(2) > table > tbody tr > td > table > tbody"
    

    def openBarcode(self, driver, store):
        loadPage(driver, "https://segaretro.org/index.php?title={}".format(store.release.barcode))
        store.concept.name = driver.find_element_by_css_selector("#p-cactions > h2").text
        store.concept.urls.append(driver.current_url)
        store.release.date = Date(self.readDate(driver))
        return store
        
    def readDate(self, driver):
        dateRow = driver.find_element_by_css_selector(self.date_selector).find_element_by_xpath("tr/td[text() = ' FR ']/..")
        return dateRow.find_element_by_css_selector("span[itemprop=datePublished]").text


class Wikipedia:
    devSelector = "#mw-content-text > div > table.infobox.hproduct > tbody" \
                  " > tr:nth-child(3) > th > a"
    publisherSelector = "#mw-content-text > div > table.infobox.hproduct > tbody" \
                        " > tr:nth-child(4) > th > a"

    def openName(self, driver, store):
        loadPage(driver,
                 "https://www.google.fr/search",
                 {
                    "q": "{} site:{}".format(store.concept.name+" (video game)", "en.wikipedia.org"),
                    "btnI": "I",
                 })

        store.concept.urls.insert(0, driver.current_url)
        store.concept.developer = scrapValue(driver, self.devSelector, "Developer(s)")
        store.release.publisher = scrapValue(driver, self.publisherSelector, "Publisher(s)")
    

def listFiles(folder, extension):
    return [os.path.abspath(path) for path in glob.glob(os.path.join(folder, "*.{}".format(extension)))]


class Collecster:
    domain = "http://collecster.adnn.fr/admin/advideogame/"
    homeTitle = "Advideogame administration | Django site admin"
    concept = {
        "urls" : {
            "table": "#concepturl_set-group > div > fieldset > table > tbody",
            "field": "#id_concepturl_set-{index}-url",
        }
    }
    release = {
        "attributes": {
            "table": "#attributes-group > div > fieldset > table > tbody",
            "field": "#id_attributes-{index}-attribute",
        }
    }
    occurrence = {
        "pictures": {
            "table": "#pictures-group > div > fieldset > table > tbody"
        }
    }

    def __init__(self, config):
        self.config = config


    def prefillConcept(self, driver, concept):
        addConcept = loadPage(driver, self.domain+"concept/add/")
        addConcept.setText("Distinctive name", concept.name)
        addConcept.setSelect("Primary nature", self.config.concept["nature"])
        addConcept.setSelect("Developer", concept.developer)
        addConcept.setInlines(self.concept["urls"], concept.urls)

    def prefillRelease(self, driver, store):
        addRelease = loadPage(driver, self.domain+"release/add/")
        addRelease.requireSelect("Concept", store.concept.name)
        store.release.date.fill(addRelease)
        addRelease.setText("Barcode", store.release.barcode)
        addRelease.setSelect("Release regions", self.config.release["release_region"])
        addRelease.setSelect("System specification", self.config.release["system_specification"])
        addRelease.setInlines(self.release["attributes"], self.config.release["attributes"])
        addRelease.setText("software-0-publisher", store.release.publisher)

    def prefillOccurrence(self, driver, store, file_iterator):
        addOccurrence = loadPage(driver, self.domain+"occurrence/add/")
        addOccurrence.requireSelect("Release", store.concept.name)
        addOccurrence.requireSelect("Origin", self.config.occurrence["origin"])
        input("Press enter to insert pictures...")

        addOccurrence.extendInlines(self.occurrence["pictures"]["table"], len(self.config.occurrence["pictures"]))
        for index, picture_guide in enumerate(self.config.occurrence["pictures"]):
            addOccurrence.setText("pictures-{index}-image_file".format(index=index), file_iterator.__next__())
            for field, value in picture_guide.items():
                addOccurrence.setSelect(field.format(index=index), value)

        addOccurrence.setSelect("operationalocc-0-working_condition", self.config.occurrence["working_condition"])

    def login(self, driver, login_filepath):
        login = loadPage(driver, self.domain)
        if os.path.exists(login_filepath):
            credentials = json.load(open(login_filepath))
            login.dictToFields(credentials)
            login.submit("login-form")
        waitForTitle(driver, self.homeTitle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adhoc templating for Collecster")
    parser.add_argument("barcode", type=int, help="The game barcode.")
    parser.add_argument("picturefolder", help="A folder containing the pictures to be added to Occurrences.")
    parser.add_argument("--credentials-file", default="credentials.json", 
                        help="A JSON file with 'username' and 'password' keys")
    args = parser.parse_args()

    # Create Chrome driver
    driver = webdriver.Chrome()

    try:
        openWindow(driver)
        openWindow(driver)
        handles = driver.window_handles

        collecster = Collecster(TemplateConfig())
        collecster.login(driver, args.credentials_file)

        driver.switch_to_window(handles[1])
        store = Store()
        store.release.barcode = args.barcode

        segaRetro = SegaRetro()
        segaRetro.openBarcode(driver, store)


        driver.switch_to_window(handles[2])
        wikipedia = Wikipedia()
        wikipedia.openName(driver, store)

        print(store)

        driver.switch_to_window(handles[0])
        collecster.prefillConcept(driver, store.concept)

        input("Press any key to exit...")

    except e:
        input("Error: {}".format(e))

    finally:
        driver.quit()

