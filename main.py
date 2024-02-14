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
import pathlib #to ensure files exist
from datetime import datetime
import mobile_functions
from mobile_functions import multiple_link_on_multiple_pages_data
from mobile_functions import concatenate_dfs
from mobile_functions import create_summary
import os
import glob




def main(read_only = False):
    MAKE_MODEL_PATH = r"./data/make_and_model_links.csv"
    
    #If the car database exists, do not update it - else, if it does not exist, create it
    if pathlib.Path(MAKE_MODEL_PATH).is_file():
        print("Make-model database already exists. Using existing file")
        pass
    else:
        get_all_make_model(save_filename = MAKE_MODEL_PATH)
    
    #Read the file we just created in again. Note that it should be ensured a "relevant" column exists, and it is filled with "x" for relevant models
    make_model_data = pd.read_csv(MAKE_MODEL_PATH)
    selected_rows = make_model_data = make_model_data.loc[make_model_data["Relevant"] == "x",:]
    
    #For debugging only - so it runs faster
    #selected_rows = selected_rows.sample(2)
    #print(selected_rows)

    if read_only == True:
        make_model_ads_data = pd.read_csv("data/make_model_ads_links_concatenated.csv")
    else:
        #Note that "multi_data" saves the data for selected makes and models automatically as csv and pickle files
        #The following extracts all adverts for the selected rows
        multi_data = multiple_link_on_multiple_pages_data(make_model_input_links =selected_rows["link"], make_model_input_data = selected_rows)

        #Combine the selected pickle / csv files (I use pickle to save the dataframe because it is faster and smaller than csv)
        make_model_ads_data = concatenate_dfs(indir= "data/make_model_ads_links/", save_to_csv = True, save_to_pickle = False)
        #make_model_ads_data = pd.read_pickle("data/make_model_ads_links_concatenated.pkl")

    #The following part should be run if detailed information about the ads (like Hubraum, etc.) is also useful
    #get_ad_data
    
    summarized_df = create_summary(make_model_ads_data, save_to_csv = True)
    





if __name__ == "__main__":
    main(read_only = False)
