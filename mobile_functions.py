""" This file contains helper functions for the scraping of mobile.de"""

#Import the required modules. Selenium is required for the scraping
import os
import glob
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import re
from random import randrange
from tqdm import tqdm #progress bar
from datetime import datetime
from datetime import date




def get_all_make_model(mobile_de_eng_base_link="https://www.mobile.de/?lang=en", save_filename="make_and_model_links.csv"):
    """ This function extracts the 'mobile.de internal' codes for makes and models. These codes need to be known in order to build search queries and scrape later on.
     This function does not need to be run every time when scraping. Once is enough, and whenever it is suspected that mobile.de updated the mappings """
    #Open the website
    chrome_options = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=chrome_options)

    driver.get(mobile_de_eng_base_link)
    time.sleep(3)
    #Get the code of the website using an HTML parser
    base_source = driver.page_source
    base_soup = BeautifulSoup(base_source, 'html.parser')

    #Get the list of car brands / makes
    make_list = base_soup.findAll('div', {"class": "k18De"})[0]
    one_make = make_list.findAll('option')

    car_make = []
    id1 = []

    for i in range(len(one_make)):

        car_make.append(one_make[i].text.strip())

        try:
            id1.append(one_make[i]['value'])
        except:
            id1.append('')

    #Convert to a dataframe
    car_base_make_data = pd.DataFrame({'car_make': car_make, 'id1': id1})

    #Filter out some not required drop-down options since they are not models
    car_make_filter_out = ['Any', 'Other', '']
    car_base_make_data = car_base_make_data[~car_base_make_data.car_make.isin(car_make_filter_out)]
    car_base_make_data = car_base_make_data.drop_duplicates()
    car_base_make_data = car_base_make_data.reset_index(drop=True)

    car_base_model_data = pd.DataFrame()

    #The below for loop loops over all car makes / brands and checks which options the drop-down menu has for "models"
    for one_make in tqdm(car_base_make_data['car_make'], "Progress: "):

        #This here finds the drop down and fills the selected make in it, and then clicks
        make_string = "//select[@name='mk']/option[text()='{}']".format(one_make)
        driver.find_element_by_xpath(make_string).click()
        time.sleep(3)

        base_source = driver.page_source
        base_soup = BeautifulSoup(base_source, 'html.parser')

        #Extract the model options
        model_list = base_soup.findAll('div', {'class': 'form-group'})[1]
        models = model_list.findAll('option')

        car_model = []
        id2 = []

        for i in range(len(models)):

            car_model.append(models[i].text.strip())

            try:
                id2.append(models[i]['value'])
            except:
                id2.append('')

        car_base_model_data_aux = pd.DataFrame({'car_model': car_model, 'id2': id2})
        car_base_model_data_aux['car_make'] = one_make

        #Create a dataframe
        car_base_model_data = pd.concat([car_base_model_data, car_base_model_data_aux], ignore_index=True)

    car_data_base = pd.merge(car_base_make_data, car_base_model_data, left_on=['car_make'], right_on=['car_make'], how='right')
    car_data_base = car_data_base[~car_data_base.id2.isin([""])]
    car_data_base = car_data_base[car_data_base.id2.apply(lambda x: x.isnumeric())]
    car_data_base = car_data_base.drop_duplicates()
    
    #This creates a link that is the starting point for a search for a given make and model
    car_data_base['link'] = "https://suchen.mobile.de/fahrzeuge/search.html?dam=0&isSearchRequest=true&ms=" + car_data_base['id1'] + ";" + car_data_base['id2'] +  "&ref=quickSearch&sfmr=false&vc=Car"
    car_data_base = car_data_base.reset_index(drop=True)

    if len(save_filename) > 0:
        car_data_base.to_csv(save_filename, encoding='utf-8', index=False)

    return(car_data_base)


def find_last_page(soup):
    """Function to find the last page of results"""
    "Find all buttons"
    all_buttons = soup.findAll('button')
    "Loop over all buttons, and find the button that says 'Next page': The last page is right before it, so extract that element"
    j = 0
    more_than_one_page = False
    for elem in all_buttons:
        j = j + 1
        "Try-except because some buttons do not have the data-testid element and would throw errors"
        try:
            if elem["data-testid"] == "pagination:next":
                more_than_one_page = True
        except:
            pass
    "If statement, because some pages have only one page and then do not even show page buttons - which would result in this function returning nothing / an error when converting to int"
    if more_than_one_page == True:
        last_button = all_buttons[j-2].text
        if last_button == "Weitere Angebote":
            last_button = int(all_buttons[j-3].text)
        else:
            last_button = int(all_buttons[j-2].text)
    else:
        last_button = 1
    return int(last_button)



def scrape_links_for_one_make_model(make_model_input_link, make_model_input_data, sleep = 1,  save_to_csv = True):
    """ This function finds the car-ad links for a selected make-model combination. E.g. it finds the links to all offers for Porsche 911 on mobile.de
    Note that it also extracts prices and titles of the ads"""

    #Start the browser
    chrome_options = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images": 2} # this is to not load images
    chrome_options.add_experimental_option("prefs", prefs)

    #start a driver
    driver = webdriver.Chrome(options=chrome_options)

    #get the number of pages
    driver.get(make_model_input_link)
    make_model_link_lastpage_source = driver.page_source
    make_model_link_soup = BeautifulSoup(make_model_link_lastpage_source, 'html.parser')

    last_button_number = find_last_page(make_model_link_soup)
   
    driver.close()

    #start scraping the ads
    
    links_on_multiple_pages = []
    prices_on_multiple_pages = []
    titles_on_multiple_pages = []

    for i in tqdm(range(1, last_button_number + 1)):

        #start a new driver every time
        #we need this to avoid getting blocked by the website. If we don't do this, we will get captcha
        chrome_options = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images": 2} # this is to not load images
        chrome_options.add_experimental_option("prefs", prefs)

        #start a driver
        driver = webdriver.Chrome(options=chrome_options)

        #we need to navigate to the page
        one_page_link = make_model_input_link + "&pageNumber=" + str(i)

        driver.get(one_page_link)
        time.sleep(sleep)
        base_source = driver.page_source
        base_soup = BeautifulSoup(base_source, 'html.parser')

        #get all the links
        cars_add_list_all = base_soup.findAll('a', {'data-testid': re.compile("result")})
        #get all the prices
        prices_all = base_soup.findAll('span', {'data-testid': re.compile("price-label")})
        #get all the titles
        titles_all = base_soup.findAll("h2")


        links_on_one_page = []
        prices_on_one_page = []
        titles_on_one_page = []


        for i in range(len(cars_add_list_all)):
            #Note that Mobile has links start with '/fahrzeuge' internally. We need an http link, so we need to add 'suchen.mobile.de' in front
            link = "https://suchen.mobile.de"+cars_add_list_all[i]['href']
            
            if not link.endswith('SellerAd'):
                # filter out links that end with 'SellerAd' (these are links to ads and we do not need them)
                links_on_one_page.append(link)

                #extract price. Note that a regular expression is needed to filter out the currency symbols. We assume all is euro
                price_field = prices_all[i].text
                remove_currency = re.compile(r"[^\d]+")
                #Assign price and currecny
                price = int(remove_currency.sub("", price_field))
                prices_on_one_page.append(price)
                titles_on_one_page.append(titles_all[i].text)

        for elements in links_on_one_page:
            links_on_multiple_pages.append(elements)
        for elements in prices_on_one_page:
            prices_on_multiple_pages.append(elements)
        for elements in titles_on_one_page:
            titles_on_multiple_pages.append(elements)

        driver.close() #close the driver

    links_on_one_page_df = pd.DataFrame({'ad_link' : links_on_multiple_pages})
    links_on_one_page_df['price'] = prices_on_multiple_pages
    links_on_one_page_df['title'] = titles_on_multiple_pages
    #drop duplicates
    links_on_one_page_df = links_on_one_page_df.drop_duplicates()

    links_on_one_page_df['make_model_link'] = make_model_input_link #via this we can see which make and model the links belong to
    links_on_one_page_df['make_model_link'] = make_model_input_link
    
    #datetime string
    now = datetime.now() 
    datetime_string = str(now.strftime("%Y%m%d_%H%M%S"))

    links_on_one_page_df['download_date_time'] = datetime_string

    #Extract make and model to save as csv
    car_make = make_model_input_data.loc[make_model_input_data["link"] == make_model_input_link,"car_make"].iloc[0]
    car_model = make_model_input_data.loc[make_model_input_data["link"] == make_model_input_link,"car_model"].iloc[0]
    
    #check if the make and model is in the dataframe
    if isinstance(make_model_input_data, pd.DataFrame):
        #join the dataframes to get make and model information
        links_on_one_page_df = pd.merge(links_on_one_page_df, make_model_input_data, how = 'left', left_on= ['make_model_link'], right_on = ['link'])

    #clean the dataframe - drop not needed columns
    links_on_one_page_df.drop(["make_model_link", "Relevant"], axis = 1)

    #Get date of today
    today = date.today()

    #save the dataframe if save_to_csv is True
    if save_to_csv:
        #check if folders exist and if not create them
        if not os.path.exists('data/make_model_ads_links'):
            os.makedirs('data/make_model_ads_links')
        if not os.path.exists("data/make_model_ads_links/{}".format(today)):
            os.makedirs("data/make_model_ads_links/{}".format(today))

        links_on_one_page_df.to_csv(str('data/make_model_ads_links/{}/{}_{}_{}'.format(today, car_make, car_model, ".csv")), index = False)

    return(links_on_one_page_df)


def multiple_link_on_multiple_pages_data(make_model_input_links, make_model_input_data, sleep = 1, save_to_csv = True):
    """ This is a wrapper that loops over all selected make-model combinations. E.g. a dataframe series containing links"""
    multiple_make_model_data = pd.DataFrame()

    #Loop over the links pointing to page 1 for each make-model combination and scrape the data for the given make-model combination
    for one_make_model_link in make_model_input_links:
        
        one_page_adds = scrape_links_for_one_make_model(make_model_input_link = one_make_model_link, sleep = sleep, make_model_input_data = make_model_input_data, save_to_csv = save_to_csv)
        multiple_make_model_data = pd.concat([multiple_make_model_data, one_page_adds], ignore_index=True)
    
    return(multiple_make_model_data)


def concatenate_dfs(indir, save_to_csv = True, save_to_pickle = True):
    """Function to concatenate the dataframes in one folder to get one file (with different columns)"""
    
    #Define the directorieswhich we do NOT want to read in. Note that any files in the "indir" directly will also NOT be read in
    #Only files in subfolders will be read
    dirs_to_drop = ["archive"]

    #Define a list of files
    file_list = []
    for subdir, dirs, files in os.walk(indir):
            for file in files:
                #if the file is in any of the dirs to drop or in the root directory, do not add it to the list
                in_dirs_to_drop = any(dir in subdir for dir in dirs_to_drop)
                if subdir == indir:
                    in_dirs_to_drop = True
                if in_dirs_to_drop:
                    pass
                else:
                    file_list.append(os.path.join(subdir, file))

    print("Found this many CSVs: ", len(file_list), " In the subdirectories of this folder: ", str(os.getcwd()) + "/" + str(indir))


    output_file = pd.concat([pd.read_csv(filename) for filename in file_list])

    if save_to_csv:
        output_file.to_csv("data/make_model_ads_links_concatenated.csv", index=False)

    if save_to_pickle:
        output_file.to_pickle("data/make_model_ads_links_concatenated.pkl")

    return(output_file)



def get_ad_data(ad_link = '', sleep_time = 5, save_to_csv = True, save_to_pickle = True):
    """For a given link to a mobile.de Car advert, extract the relevant data"""
    chrome_options = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images": 2} # this is to not load images
    chrome_options.add_experimental_option("prefs", prefs)

    #start a driver
    driver = webdriver.Chrome(options=chrome_options)

    #get the page data
    driver.get(ad_link)
    time.sleep(sleep_time)
    ad_source = driver.page_source
    ad_soup = BeautifulSoup(ad_source, 'html.parser')
    driver.close()

    #Get the part of the page that houses the characteristics
    try:
        table_pre = ad_soup.find("div", { "class" : "cBox-body cBox-body--technical-data"})
        all_div = table_pre.findAll("div", { "class" : re.compile('^g-col-6')})
    except:
        table_pre = []
        all_div = []
    
    description_list = []
    value_list = []

    try:
        div_length = len(all_div)
    except:
        div_length = 2

    #Add the characteristics and their values to two lists. Note that range increases by 2 since one element is the description, the next one the value, etc.
    for i in range(0,div_length - 1,2):
        try:
            description_list.append(all_div[i].text.strip())
            value_list.append(all_div[i+1].text.strip())
        except:
            description_list.append('no_description')
            value_list.append('no_value')
            # Add price and currency
    try:
        #Extract the price field
        price_field = price_field = ad_soup.find("span", {"data-testid" : "prime-price"}).text

        #Define regular expressions to extract price and currency
        remove_currency = re.compile(r"[^\d]+")
        currency_filter = re.compile(r"[\d+\s|\s\d+\s|\s\d|\\.]+")

        #Assign price and currecny
        price = int(remove_currency.sub("", price_field))
        currency = currency_filter.sub("", price_field)

        description_list.append("Preis")
        description_list.append("Währung")

        value_list.append(price)
        value_list.append(currency)
    except:
        #pass, since we already have above "no description" exception
        pass

    

    #create a dataframe
    df = pd.DataFrame(list(zip(description_list, value_list)), columns = ['description', 'value'])

    #keep rows where value is equal to the followings
    data_we_want_to_keep = ['Preis', "Währung", 'Kategorie', 'Kilometerstand', 'Hubraum', 'Leistung', 'Kraftstoffart', 'Anzahl Sitzplätze', 'Getriebe', 'Erstzulassung', 'Farbe', 'Innenausstattung']
    df = df[df['description'].isin(data_we_want_to_keep)]

    # #transpose with description as column names
    #df = df.T
    df = df.set_index('description').T.reset_index(drop=True)
    df = df.rename_axis(None, axis=1)
    df['link'] = ad_link

    #datetime string
    now = datetime.now() 
    datetime_string = str(now.strftime("%Y%m%d_%H%M%S"))

    df['download_date_time'] = datetime_string

    #save the dataframe if save_to_csv is True
    if save_to_csv:
        #check if folder exists and if not create it
        if not os.path.exists('data/make_model_ads_data'):
            os.makedirs('data/make_model_ads_data')

        df.to_csv(str('data/make_model_ads_data/links_on_one_page_df' + datetime_string + '.csv'), index = False)

    if save_to_pickle:
        if not os.path.exists('data/make_model_ads_data'):
            os.makedirs('data/make_model_ads_data')
        
        df.to_pickle('data/make_model_ads_data/links_on_one_page_df' + datetime_string + "pkl")

    return(df)

def create_summary(make_model_ads_data, save_to_csv):
    """Function to summarize the car brand and model data. Input is a list of posts on mobile.de. 
    This function returns an overview by make, model, and date that reports the number of listings and change compared to the previous timestep"""

    #Create a date column - the datetime column, except the last 7 characters
    make_model_ads_data["date"] = make_model_ads_data["download_date_time"].str[:-7]
    make_model_ads_data["date"] = pd.to_datetime(make_model_ads_data["date"], format = "%Y%m%d")

    #Remove duplicate rows. We assume duplicate rows are rows of the same model, make, date, price, and title
    make_model_ads_data = make_model_ads_data.drop_duplicates(subset=["car_make", "car_model", "date", "title", "price"])

    #Summarize the dataframe by getting count, avg. price, and sd of price
    summarized_df = make_model_ads_data.groupby(["car_make","car_model","date"])\
                                        .agg(count = ("make_model_link","size"), mean_price = ("price","mean"),sd_price = ("price", "std"))
    
    #Get the links of the ads that are online at a given date for a given car and model. Note, duplicates are removed (see above)
    #Not doing it by titles because they are not always unique - e.g. Porsche 911 is used more than once as a title, for different offers
    ads_online = make_model_ads_data.groupby(["car_make","car_model","date"])['ad_link'].agg(set)
    
    #Based on the unique ad-links (after duplicates were dropped) get the new advertisements compared to the last date
    #And also get the advertisements that used to exist but not anymore
    ads_online_new = ads_online.diff().str.len().fillna(0).convert_dtypes()
    ads_online_sold = ads_online.diff(-1).str.len().fillna(0).convert_dtypes()
    
    #Create columns "new" and "sold" that are the ads_online_new and ads_online_sold from above
    summarized_df['new'] = summarized_df.merge(ads_online_new, left_index=True, right_index=True)["ad_link"]
    summarized_df['sold'] = summarized_df.merge(ads_online_sold, left_index=True, right_index=True)["ad_link"]

    #Sort by Date
    summarized_df.sort_values(by = "date")

    #Ensure that the last element of the "sold" series, and the first element of the "new" series are 0 for car - model
    summarized_df.loc[summarized_df.groupby(["car_make","car_model"])["new"].nth(0).index,"new"] = 0
    summarized_df.loc[summarized_df.groupby(["car_make","car_model"])["sold"].nth(-1).index,"sold"] = 0

    summarized_df.to_csv("results.csv")

    return(summarized_df)


