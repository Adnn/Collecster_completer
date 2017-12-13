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
import time


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


def insideOutmostQuotes(text):
    result = text[text.index('"')+1:]
    result = result[:result.rfind('"')]
    return result


def listFiles(folder, extension):
    return [os.path.abspath(path) for path in glob.glob(os.path.join(folder, "*.{}".format(extension)))]


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

        self.scrappers = {
            "segaretro": {
                "date-system-title": "Sega Master System",
            },
            "giantbomb": {
                "system-abbreviation": "SMS",
            }
        }


class Concept:
    def __init__(self):
        self.urls = []
        self.developer = None
    pass

class Release:
    def __init__(self):
        self.publisher = None
        self.barcode = None

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
        
    def _fieldNameToId(self, name):
       return "id_{}".format(name.lower().replace(" ", "_")) 

    def _checkValue(self, field_name, value):
        # The value could be an int, cast anyway
        splitted = str(value).split("\n")
        if len(splitted) > 1:
            print(colored("Field {} receives multiple values. First one, '{}', will be used. The complete list:\n\t*{}"
                                .format(field_name, splitted[0], "\n\t*".join(splitted)), "yellow"))
        return splitted[0]

    def findField(self, field_name):
        return self.driver.find_element_by_id(self._fieldNameToId(field_name))

    def fillText(self, element, value):
        element.send_keys(value)

    def fillSelect(self, element, value):
        Select(element).select_by_visible_text(value)

    def setText(self, field_name, value):
        self.fillText(self.findField(field_name), self._checkValue(field_name, value))

    def setSelect(self, field_name, value):
        try:
            self.fillSelect(self.findField(field_name), self._checkValue(field_name, value))
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
    #date_selector = "#mw-content-text > div:nth-child(2) > table > tbody tr > td > table > tbody"
    date_selector = "#mw-content-text > div > table.breakout > tbody tr > td > table > tbody"
    
    def __init__(self, config):
        self.config = config.scrappers["segaretro"]

    def lookup(self, driver, lookup_value):
        loadPage(driver, "https://segaretro.org/index.php?title={}".format(lookup_value))
        try:
            driver.find_element_by_css_selector("div.noarticletext")
            return None
        except NoSuchElementException:
            return driver.current_url

    def scrapCurrentPage(self, driver, store):
        store.concept.name = driver.find_element_by_css_selector("#p-cactions > h2").text
        store.concept.urls.append(driver.current_url)
        store.release.date = Date(self.readDate(driver))
        return store

    def readDate(self, driver):
        dateRow = driver.find_element_by_css_selector(self.date_selector) \
                    .find_element_by_xpath("tr/td[text() = ' FR ']/div/a[@title='{}']/../../.."
                        .format(self.config["date-system-title"]))
        value = dateRow.find_element_by_css_selector("span[itemprop=datePublished]").text
        # Dates on Sega Retro can be followed by a number between square brackets. We get rid of this suffix.
        if "[" in value:
            return value[:value.index("[")]
        else:
            return value


class Wikipedia:
    devSelector = "#mw-content-text > div > table.infobox.hproduct > tbody" \
                  " > tr > th > a[title=\"Video game developer\"]"
    publisherSelector = "#mw-content-text > div > table.infobox.hproduct > tbody" \
                        " > tr > th > a[title=\"Video game publisher\"]"

    def openName(self, driver, store):
        loadPage(driver,
                 "https://www.google.fr/search",
                 {
                    "q": "{} site:{}".format(store.concept.name+" (video game)", "en.wikipedia.org"),
                    "btnI": "I",
                 })

    def scrapValues(self, driver, store):
        # Note: simulate atomic operation by first attempting all operation that could reasonably fail, before
        # commiting to the store variable
        developer = scrapValue(driver, self.devSelector, "Developer(s)")
        publisher = scrapValue(driver, self.publisherSelector, "Publisher(s)")
        url = driver.current_url

        store.concept.urls.insert(0, url)
        store.concept.developer = developer
        store.release.publisher = publisher


class GiantBomb:
    origin = "https://www.giantbomb.com"
    search_query = "/search/?indices[0]=game&page=1&q=spy%20vs%20spy"

    def __init__(self, config):
        self.config = config.scrappers["giantbomb"]

    def openName(self, driver, store):
        loadPage(driver, self.origin + "/search",
                 {
                    "indices[0]": "game",
                    "q": store.concept.name,
                 })

        xpath = "//span[@class=\"search-platform\"][contains(text(), \"{platform}\")]"
        driver.find_element_by_xpath(xpath.format(platform=self.config["system-abbreviation"])) \
                .click()

    def scrapValues(self, driver, store):
        # Just a check that will throw is the found page is not what was expected
        driver.find_element_by_xpath(
                "//*[@id=\"default-content\"]/aside/div[@class=\"wiki-details\"]/h3[text()='Game details']")
        url = driver.current_url

        store.concept.urls.append(url)


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
    success_selector = "#container > ul.messagelist > li.success"

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
        addRelease.requireSelect("Concept", store.concept.saved_name)
        time.sleep(1) # Naive wait for AJAX
        store.release.date.fill(addRelease)
        addRelease.setText("Barcode", store.release.barcode)
        addRelease.setSelect("Release regions", self.config.release["release_region"])
        addRelease.setSelect("System specification", self.config.release["system_specification"])
        addRelease.setInlines(self.release["attributes"], self.config.release["attributes"])
        addRelease.setSelect("software-0-publisher", store.release.publisher)

    def prefillOccurrence(self, driver, store, file_iterator):
        addOccurrence = loadPage(driver, self.domain+"occurrence/add/")
        addOccurrence.requireSelect("Release", store.release.saved_name)
        time.sleep(1) # Naive wait for AJAX
        addOccurrence.setSelect("Origin", self.config.occurrence["origin"])
        addOccurrence.setSelect("operationalocc-0-working_condition", self.config.occurrence["working_condition"])

        input("Press enter to insert pictures...")
        addOccurrence.extendInlines(self.occurrence["pictures"]["table"], len(self.config.occurrence["pictures"]))
        for index, picture_guide in enumerate(self.config.occurrence["pictures"]):
            addOccurrence.setText("pictures-{index}-image_file".format(index=index), file_iterator.__next__())
            for field, value in picture_guide.items():
                addOccurrence.setSelect(field.format(index=index), value)

    def login(self, driver, login_filepath):
        login = loadPage(driver, self.domain)
        if os.path.exists(login_filepath):
            credentials = json.load(open(login_filepath))
            login.dictToFields(credentials)
            login.submit("login-form")
        waitForTitle(driver, self.homeTitle)

    def waitSuccessConfirmation(self, driver):
        WebDriverWait(driver, 360000).until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, self.success_selector), "was added successfully"))
        success_text = driver.find_element_by_css_selector(self.success_selector).text
        return insideOutmostQuotes(success_text)


def retryScrap(driver, website, website_name, store):
    scrap_on = True
    while scrap_on:
        try:
            website.scrapValues(driver, store)
            scrap_on = False #No exception thrown means scraping was successful
        except Exception as e:
            command = input("Scrapping failed from {} window.".format(website_name) +
                            " Try navigation manually to the right page then press enter, or type 's' to skip...")
            scrap_on = (command != "s")


def recordGame(driver, handles, config, args, file_iterator, barcode=None, lookup=None):
    store = Store()
    if barcode:
        store.release.barcode = barcode
        lookup = barcode

    driver.switch_to_window(handles["segaretro"])
    segaRetro = SegaRetro(config)
    if (not lookup) or (not segaRetro.lookup(driver, lookup)):
        return False
    segaRetro.scrapCurrentPage(driver, store)

    if not args.skip_wikipedia:
        driver.switch_to_window(handles["wikipedia"])
        wikipedia = Wikipedia()
        wikipedia.openName(driver, store)
        retryScrap(driver, wikipedia, "Wikipedia", store)
    else:
        store.concept.developer = input("Please enter developer: ")
        store.release.publisher = input("Please enter publisher: ")

    if args.verbose:
        print(store)


    driver.switch_to_window(handles["giantbomb"])
    giantbomb = GiantBomb(config)
    giantbomb.openName(driver, store)
    retryScrap(driver, giantbomb, "GiantBomb", store)

    driver.switch_to_window(handles["collecster"])

    if (not args.concept) and (not args.release):
        collecster.prefillConcept(driver, store.concept)
        store.concept.saved_name = collecster.waitSuccessConfirmation(driver)
    else:
        store.concept.saved_name = args.concept
    print("Saved concept name: {}".format(store.concept.saved_name))

    if not args.release:
        collecster.prefillRelease(driver, store)
        store.release.saved_name = collecster.waitSuccessConfirmation(driver)
    else:
        store.release.saved_name = args.release
    print("Saved release name: {}".format(store.release.saved_name))

    collecster.prefillOccurrence(driver, store, file_iterator)
    collecster.waitSuccessConfirmation(driver)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adhoc templating for Collecster")
    parser.add_argument("picturefolder", help="A folder containing the pictures to be added to Occurrences.")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--barcode", type=int, help="The game barcode.")
    group.add_argument('--name', help="The game name.")
    group.add_argument('--interactive', action="store_true",
                       help="Launch in interactive mode, where the application ask for barcodes in a loop.")

    parser.add_argument("--credentials-file", default="credentials.json", 
                        help="A JSON file with 'username' and 'password' keys")
    parser.add_argument("--concept", help="If a concept name is given, no concept will be created.")
    parser.add_argument("--release", help="If a release name is given, no concept nor release will be created.")

    parser.add_argument("-s", "--skip-wikipedia", action="store_true", help="Prevents the Wikipedia scrapper.")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Prints the store content as it was scrapped from the sources.")

    args = parser.parse_args()

    # Create Chrome driver
    driver = webdriver.Chrome()

    windowCount = 4
    if (args.skip_wikipedia):
        windowCount -= 1

    for i in range(windowCount-1):
        openWindow(driver)
    handles = {
        "collecster": driver.window_handles[0],
        "segaretro":  driver.window_handles[1],
        "wikipedia":  driver.window_handles[2],
        "giantbomb":  driver.window_handles[3],
    } 

    config = TemplateConfig()

    file_iterator = iter(listFiles(args.picturefolder, "jpg"))

    try:
        collecster = Collecster(config)
        collecster.login(driver, args.credentials_file)

        if args.barcode or args.name:
            recordGame(driver, handles, config, args, file_iterator, args.barcode, args.name)
            input("Success! Press any key to exit...")

        elif args.interactive:
            while(True):
                barcode = input("Please enter barcode (Ctrl+C to stop): ")
                name = None
                if not barcode:
                    name = input("Please enter name (Ctrl+C to stop): ")
                success = recordGame(driver, handles, config, args, file_iterator, barcode, name)
                if not success:
                    print("Could not find a game for provided parameters")

        else:
            raise Exception("Unimplemented mode")

    except Exception as e:
        input("Error: {}".format(e))

    finally:
        driver.quit()

