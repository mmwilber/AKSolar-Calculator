
import os
import io
import math
import functools
import urllib
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import requests

#import matplotlib.pyplot as plt

# Most of the data files are located remotely and are retrieved via
# an HTTP request.  The function below is used to retrieve the files,
# which are Pandas DataFrames

# The base URL to the site where the remote files are located
base_url = 'http://ak-energy-data.analysisnorth.com/'


# # Use some of Alan Mitchells's code from the heat pump calculator (github) to download tmy files for hourly temperature

def get_df(file_path):
    """Returns a Pandas DataFrame that is found at the 'file_path'
    below the Base URL for accessing data.  The 'file_path' should end
    with '.pkl' and points to a pickled, compressed (bz2), Pandas DataFrame.
    """
    b = requests.get(urllib.parse.urljoin(base_url, file_path)).content
    df = pd.read_pickle(io.BytesIO(b), compression='bz2')
    return df

#load a file with tmy summary info including the best tilt for a solar panel:
df = pd.read_csv('AKtmy_summary.csv', parse_dates = True, index_col = 'tmy_id')

#load a file with pvwatts monthly solar production for tmy3 stations in AK, based on tilt:
results_df = pd.read_csv('AKtmy_monthlyprod.csv', parse_dates = True, index_col = 0)
#these are the tilts used:
#tilts = [14,18.4,22.6,26.6,30,45,df['best_tilt'].loc[df.index == tmyid].iloc[0],90] 

st.image(['ACEP.png'])
st.title("Alaska Solar PV Sizing and Payback Calculator")
st.write("")
st.write("This is a calculator to find optimal sizing and economic payback for a behind-the-meter PV system in Alaska.")

st.write("Community and Utility data are taken from http://ak-energy-data.analysisnorth.com/ ")

#location
#get the Alaska city data
# Access as a Pandas DataFrame
dfc = get_df('city-util/proc/city.pkl')

# User Input

#create a drop down menu of the available communities and find the corresponding TMYid
cities = dfc['aris_city'].drop_duplicates().sort_values(ignore_index = True) #get a list of community names
city = st.selectbox('Select your community:', cities ) #make a drop down list and get choice
tmyid = dfc['TMYid'].loc[dfc['aris_city']==city].iloc[0] #find the corresponding TMYid

#User input: choose a tilt, enter cost info, etc:
tilts = [14,18.4,22.6,26.6,30,45,df['best_tilt'].loc[df.index == tmyid].iloc[0],90]

tilt = st.selectbox('Choose a tilt in degrees for your panels:', tilts ) #make a drop down list and get choice
st.write("Note: the first 4 choices correspond to roof slopes of 3 in 12, 4 in 12 etc.  The second to last choice is the optimum tilt for your location according to NREL's PVWatts calculator. 90 degrees is vertical.")
st.write("")
taxr = st.selectbox('Select a solar tax credit amount, 26% for installation in 2022, 22% for 2023:', [26,22] )/100 #make a drop down list and get choice.26 #26 in 2022, 22% in 2023

life = st.slider('What is the life of your system?', max_value = 30, value = 20)
cost = st.slider('What is the cost of your system per installed watt (this may depend on the size of the system)?', max_value = 9, value = 3)
def_size = 3 #will need this later if not a net metered system


#find the production at that tilt and location:
unit_prod = results_df.loc[(results_df['tmy_id'] == tmyid) & (results_df['tilt'] == tilt)].iloc[0,2:]
unit_prod.index = unit_prod.index.astype(int)-1

#There are two very different situations - net metered or non-netmetered!

# Access Alan's Alaska utility data as a Pandas DataFrame
dfu = get_df('city-util/proc/utility.pkl')
util = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][1] #find a utility id for the community chosen
uname = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][0] #find the utility name for the community chosen
uname = uname.split('-')[0] #that name had a rate class included, so breaking that off - check if this works!
if (dfu['PCE'].loc[dfu['ID']==util].iloc[0]==dfu['PCE'].loc[dfu['ID']==util].iloc[0]): #if utility has a PCE adjusted rate, use it
    rate_def = dfu['PCE'].loc[dfu['ID']==util].iloc[0]
else: #otherwise dig down for the non-PCE adjusted rate
    rate_def = dfu['Blocks'].loc[dfu['ID']==util].iloc[0][0][1] #at least for fairbanks this works to get a per kWh rate from the database - may not always work!

cpkwh_default = dfu['CO2'].loc[dfu['ID']==util].iloc[0]/2.2 #find the CO2 per kWh for the community and divide by 2.2 to change pounds to kg
cpkwh_default = float(cpkwh_default) 
st.write("")
st.write("According to the database, your utility is ", uname)
st.write("Always talk to your utility before adding grid-connected solar!  Each utility has its own process, and some may not be equiped to safely allow electricity to flow back on to the grid.")
st.write("Golden Valley Electric, Matanuska Electric, Chugach Electric, Seward Electric and Homer Electric allow net metering, with certain limits and an interconnection agreement")

nm = st.checkbox("Check here if your utility will allow your system to net-meter")
if nm:
    

    #choose an electric rate, avoided fuel cost,netmetered?, system life, system cost,  monthly usage
    rate = st.slider('What do you pay per kWh for electricity?', max_value = 1.0, value = rate_def)
    st.write("Note: we do not account for PCE limits, block rates, or demand charges, which could change the results.")
    copa = st.slider('What is the avoided fuel cost for your utility?', max_value = .20, value = .7, help = 'check at its website or call the utility customer service')
    st.write("This is the amount assumed to be payed for electricity sold back to your utility.")
    st.write("Input your monthly electric usage in kWh (from your bills or utility member portal) here:")
    u1 = number_input('January:')
    u2 = number_input('Febuary:')
    u3 = number_input('March:')
    u4 = number_input('April:')
    u5 = number_input('May:')
    u6 = number_input('June:')
    u7 = number_input('July:')
    u8 = number_input('August:')
    u9 = number_input('September:')
    u10 = number_input('October:')
    u11 = number_input('November:')
    u12 = number_input('December:')
    usage = pd.Series([u1,u2,u3,u4,u5,u6,u7,u8,u9,u10,u11,u12])
    
    #some calulations:
    max_size = usage/unit_prod #element-wise array calc
    def_size = min(max_size)
size = st.slider('Size of the system in kW(the default here is the system with the best payback if you have net metering)?', max_value = 25, value = def_size)
prod = size*unit_prod 


#more calcs - will want to present:
cost_sys = cost * size
st.write("Expected System Cost: $", cost_sys)
tcredit = cost_sys * taxr
st.write("Expected Tax Credit: $", tcredit)
net_cost = cost_sys - tcredit
st.write("Expected Net System Cost: $", net_cost)
st.write("Expected System Production in kWh:", sum(prod))
if nm:
    save = rate*prod #only true if net metering and for this prod l.t. consumpt
    #for net metered - where prod < usage, save = rate*prod, where prod > usage, save = usage*rate + copa*(prod - usage)
    save.where(prod < usage, usage*rate + copa*(prod-usage), inplace = True)
    annual_save = sum(save)
    st.write("Expected Annual Energy Cost Savings:", annual_save)
    simplepay = net_cost/annual_save
    st.write("Simple Payback:", simplepay)
    anualROI = (1+((life*annual_save)-net_cost)/net_cost)**(1/life)-1
    st.write("Annualizaed ROI:", annualROI)
    grid_red = sum(prod)/sum(usage)*100
    st.write("Percent reduction in Grid Energy Usage:", grid_red)







#could calculate NPV etc, take into account utility rate escalation, inflation, and degradation - maybe a little much for now!

# could look at greenhouse gas emission reductions in the future 


st.write("")

st.write("Thanks to Alan Mitchell of Analysis North for Alaskan utility data, tmy files, and wonderful code to access and use them all.")
st.write("See http://ak-energy-data.analysisnorth.com and https://github.com/alanmitchell/heat-pump-calc")
st.write("...And definitely check out the Alaskan Heat Pump Calculator at https://heatpump.cf to see if you should get a heat pump!")
st.write("")
st.write("")
st.write("Please peak under the hood at this code at https://github.com/mmwilber/AKSolar-Calculator")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
